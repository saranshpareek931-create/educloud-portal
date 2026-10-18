"""
Small SQLite-style compatibility layer for EduCloud Portal.
Uses PostgreSQL when DATABASE_URL is set, otherwise falls back to local SQLite.
"""
import os
import re
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

class HybridRow(dict):
    """Allows both row['column'] and row[0], like sqlite3.Row."""
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = tuple(values)
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

class PGCursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return HybridRow(row.keys(), row.values())
        return row
    def fetchall(self):
        rows = self._cursor.fetchall()
        converted = []
        for row in rows:
            if isinstance(row, dict):
                converted.append(HybridRow(row.keys(), row.values()))
            else:
                converted.append(row)
        return converted
    def __iter__(self):
        return iter(self.fetchall())
    @property
    def rowcount(self):
        return self._cursor.rowcount

class PGConnection:
    def __init__(self, connection):
        self._connection = connection
    def execute(self, sql, params=()):
        query = sql
        params = tuple(params or ())
        # Translate SQLite placeholders to psycopg placeholders.
        query = query.replace("?", "%s")
        # Preserve the SQLite cursor.lastrowid behavior for INSERTs with an id column.
        lastrowid = None
        if re.match(r"\s*INSERT\s+INTO\s+resources\b", query, re.I) and "RETURNING" not in query.upper():
            query = query.rstrip().rstrip(";") + " RETURNING id"
            cur = self._connection.cursor()
            cur.execute(query, params)
            got = cur.fetchone()
            if got:
                lastrowid = got[0] if not isinstance(got, dict) else got.get("id")
            return PGCursor(cur, lastrowid)
        cur = self._connection.cursor()
        cur.execute(query, params)
        return PGCursor(cur, lastrowid)
    def commit(self):
        self._connection.commit()
    def close(self):
        self._connection.close()

def connect_database():
    if not DATABASE_URL:
        conn = sqlite3.connect("educloud.db")
        conn.row_factory = sqlite3.Row
        return conn
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("psycopg[binary] is required when DATABASE_URL is set") from exc
    # Render sometimes provides postgres://; psycopg accepts postgresql://.
    dsn = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return PGConnection(psycopg.connect(dsn, row_factory=dict_row))
