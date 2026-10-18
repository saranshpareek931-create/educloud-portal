"""
Run this once from your EduCloud project folder:
    python patch_app.py
It makes a backup and changes only the database import/get_db function.
"""
from pathlib import Path
import re
import shutil
from datetime import datetime

path = Path("app.py")
if not path.exists():
    raise SystemExit("ERROR: app.py not found. Run this script from your EduCloud project folder.")

source = path.read_text(encoding="utf-8")

if "from db_compat import connect_database" in source:
    print("app.py already appears patched; no changes made.")
    raise SystemExit(0)

backup = path.with_name(f"app.py.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
shutil.copy2(path, backup)

source = source.replace("import sqlite3", "from db_compat import connect_database")

pattern = re.compile(
    r"def get_db\(\):\s*\n\s*connection = sqlite3\.connect\(DATABASE\)\s*\n\s*connection\.row_factory = sqlite3\.Row\s*\n\s*return connection",
    re.MULTILINE
)
replacement = "def get_db():\n    return connect_database()"
source, count = pattern.subn(replacement, source, count=1)
if count != 1:
    shutil.copy2(backup, path)
    raise SystemExit(
        f"Could not safely locate the exact get_db() function (matches={count}). "
        f"Original app.py restored. Backup: {backup.name}"
    )

path.write_text(source, encoding="utf-8")
print(f"Patched app.py successfully. Backup saved as {backup.name}")
