"""
One-time SQLite -> PostgreSQL migration for EduCloud.
Run from your local project folder, where educloud.db exists, with DATABASE_URL set.
This script does not delete or modify the SQLite source database.
"""
import os
import re
import sqlite3
import sys

DB_FILE = "educloud.db"
dsn = os.environ.get("DATABASE_URL", "").strip()
if not dsn:
    raise SystemExit("ERROR: Set DATABASE_URL to your Render PostgreSQL External Database URL first.")
if not os.path.exists(DB_FILE):
    raise SystemExit(f"ERROR: {DB_FILE} not found in the current folder.")

try:
    import psycopg
    from psycopg.rows import tuple_row
except ImportError:
    raise SystemExit("ERROR: Install dependencies first: pip install 'psycopg[binary]'")

dsn = dsn.replace("postgres://", "postgresql://", 1)
src = sqlite3.connect(DB_FILE)
src.row_factory = sqlite3.Row
dst = psycopg.connect(dsn, row_factory=tuple_row)

def translate_create(sql):
    # Common SQLite autoincrement primary-key forms -> PostgreSQL.
    sql = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "SERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bINT\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "SERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bAUTOINCREMENT\b", "", sql, flags=re.I)
    # SQLite accepts double-quoted identifiers; PostgreSQL does too.
    return sql

try:
    tables = src.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY CASE name
            WHEN 'branches' THEN 1
            WHEN 'years' THEN 2
            WHEN 'users' THEN 3
            WHEN 'subjects' THEN 4
            WHEN 'resources' THEN 5
            ELSE 6 END
    """).fetchall()

    if not tables:
        raise RuntimeError("No tables found in educloud.db. Make sure this is the correct database file.")

    print("Tables found:", ", ".join(t["name"] for t in tables))
    with dst.cursor() as cur:
        # Create tables only when missing; do not drop or overwrite existing tables.
        for table in tables:
            if not table["sql"]:
                continue
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)",
                (table["name"],)
            )
            exists = cur.fetchone()[0]
            if not exists:
                create_sql = translate_create(table["sql"])
                cur.execute(create_sql)
                print("Created table:", table["name"])
        dst.commit()

    # Copy rows only into empty destination tables to avoid duplicates.
    for table in tables:
        name = table["name"]
        columns = [r["name"] for r in src.execute(f'PRAGMA table_info("{name}")').fetchall()]
        rows = src.execute(f'SELECT * FROM "{name}"').fetchall()
        with dst.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{name}"')
            existing_count = cur.fetchone()[0]
            if existing_count:
                print(f"SKIP {name}: PostgreSQL already contains {existing_count} rows (not empty).")
                continue
            if not rows:
                print(f"{name}: no rows to copy")
                continue
            quoted_columns = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f'INSERT INTO "{name}" ({quoted_columns}) VALUES ({placeholders})'
            cur.executemany(insert_sql, [tuple(row[c] for c in columns) for row in rows])
            print(f"Copied {len(rows)} rows into {name}")
        dst.commit()

    # Reset serial sequences so future inserts don't collide with migrated IDs.
    with dst.cursor() as cur:
        for table in tables:
            name = table["name"]
            col_info = src.execute(f'PRAGMA table_info("{name}")').fetchall()
            pk = next((c["name"] for c in col_info if c["pk"] == 1), None)
            if pk:
                cur.execute("""
                    SELECT pg_get_serial_sequence(%s, %s)
                """, (f'public.{name}', pk))
                seq = cur.fetchone()[0]
                if seq:
                    cur.execute(f'SELECT COALESCE(MAX("{pk}"), 0) FROM "{name}"')
                    max_id = cur.fetchone()[0]
                    cur.execute("SELECT setval(%s, %s, %s)", (seq, max(max_id, 1), max_id > 0))
    dst.commit()
    print("\nMigration finished. SQLite source file was not changed.")
except Exception as exc:
    dst.rollback()
    print("\nMIGRATION STOPPED:", exc)
    print("The local SQLite database was not modified. Review the error before retrying.")
    sys.exit(1)
finally:
    src.close()
    dst.close()
