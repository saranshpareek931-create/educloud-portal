import sqlite3

DATABASE = "educloud.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


print("\n====================================")
print("       EduCloud - Add Teacher")
print("====================================\n")

name = input("Teacher name: ").strip()
username = input("Username: ").strip()
password = input("Password: ").strip()

if not name or not username or not password:
    print("\n❌ Name, username and password are required.")
    raise SystemExit

connection = get_db()

branches = connection.execute("""
    SELECT id, name, code
    FROM branches
    ORDER BY id
""").fetchall()

if not branches:
    connection.close()
    print("\n❌ No branches found in database.")
    raise SystemExit

print("\nAvailable branches:")

for branch in branches:
    print(f"{branch['id']}. {branch['name']} ({branch['code']})")

branch_input = input("\nEnter branch number: ").strip()

try:
    branch_id = int(branch_input)
except ValueError:
    connection.close()
    print("\n❌ Invalid branch number.")
    raise SystemExit

branch = connection.execute("""
    SELECT id, name, code
    FROM branches
    WHERE id = ?
""", (branch_id,)).fetchone()

if not branch:
    connection.close()
    print("\n❌ Branch not found.")
    raise SystemExit

existing = connection.execute("""
    SELECT id
    FROM users
    WHERE username = ?
""", (username,)).fetchone()

if existing:
    connection.close()
    print(f"\n❌ Username '{username}' already exists.")
    print("Please choose another username.")
    raise SystemExit

connection.execute("""
    INSERT INTO users
    (
        name,
        username,
        password,
        role,
        branch_id,
        year_id
    )
    VALUES (?, ?, ?, 'teacher', ?, NULL)
""", (
    name,
    username,
    password,
    branch_id
))

connection.commit()
connection.close()

print("\n====================================")
print("✅ Teacher added successfully!")
print("====================================")
print(f"Name     : {name}")
print(f"Username : {username}")
print(f"Branch   : {branch['name']}")
print("Role     : Teacher")
print("====================================\n")