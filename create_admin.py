import sqlite3

DATABASE = "educloud.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


print("\n====================================")
print("       EduCloud - Create Admin")
print("====================================\n")

name = input("Admin name: ").strip()
username = input("Admin username: ").strip()
password = input("Admin password: ").strip()

if not name or not username or not password:
    print("\n❌ Name, username and password are required.")
    raise SystemExit

connection = get_db()

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
    VALUES (?, ?, ?, 'admin', NULL, NULL)
""", (
    name,
    username,
    password
))

connection.commit()
connection.close()

print("\n====================================")
print("✅ Admin created successfully!")
print("====================================")
print(f"Name     : {name}")
print(f"Username : {username}")
print("Role     : Admin")
print("====================================\n")