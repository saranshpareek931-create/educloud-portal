# EduCloud: SQLite -> PostgreSQL (Render)

## Files
- `db_compat.py`: compatibility layer so existing routes can keep using `?` placeholders and `connection.execute(...)`.
- `patch_app.py`: patches only the `import sqlite3` and `get_db()` parts of your existing `app.py`, creating a timestamped backup first.
- `migrate_sqlite_to_postgres.py`: copies the local SQLite tables/data into PostgreSQL. It never deletes or edits `educloud.db`.

## Important
1. Keep a copy of `educloud.db`, `uploads/`, and `static/qr_codes/`.
2. `DATABASE_URL` must be the PostgreSQL **External Database URL** from Render when running the migration locally. Do not paste the URL into chat or commit it to GitHub.
3. The migration skips destination tables that already contain rows; it does not merge or overwrite data.
4. The schema converter handles common SQLite schemas, especially `INTEGER PRIMARY KEY AUTOINCREMENT`. If your database schema uses SQLite-specific features, the script will stop and show an error instead of deleting the source.
5. Render web services have an ephemeral filesystem by default. Uploaded files in `uploads/` and QR images in `static/qr_codes/` are not made persistent by PostgreSQL. Use a persistent disk or object storage for uploads before relying on them in production.

## Steps
1. Extract these files into your project folder (`C:\\Users\\...\\Documents\\Edu Cloud`), beside `app.py` and `educloud.db`.
2. In the project terminal:
   `python patch_app.py`
3. Ensure `requirements.txt` includes:
   `psycopg[binary]`
4. Install dependencies locally:
   `pip install -r requirements.txt`
5. Set `DATABASE_URL` in your local terminal to Render's External Database URL without sharing it publicly.
   PowerShell:
   `$env:DATABASE_URL="PASTE_RENDER_EXTERNAL_DATABASE_URL_HERE"`
6. Run migration:
   `python migrate_sqlite_to_postgres.py`
7. Test locally with the same `DATABASE_URL` set:
   `python app.py`
8. Commit/push `app.py`, `db_compat.py`, and `requirements.txt` to GitHub. Do not commit `.env` or the database URL.
9. Render should redeploy automatically. Check login, admin dashboard, teacher upload, student resources, and QR routes.

If your Render PostgreSQL database already has real data, do not run this script blindly: it skips non-empty tables, but that can leave related tables inconsistent. Stop and inspect first.
