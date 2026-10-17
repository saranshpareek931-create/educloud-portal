import sqlite3

DATABASE = "educloud.db"


def create_users():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # =========================
    # GET BRANCHES
    # =========================

    cse = cursor.execute("""
        SELECT id
        FROM branches
        WHERE code = 'CSE'
    """).fetchone()

    civil = cursor.execute("""
        SELECT id
        FROM branches
        WHERE code = 'CIVIL'
    """).fetchone()

    # =========================
    # GET YEARS
    # =========================

    first_year = cursor.execute("""
        SELECT id
        FROM years
        WHERE name = '1st Year'
    """).fetchone()

    second_year = cursor.execute("""
        SELECT id
        FROM years
        WHERE name = '2nd Year'
    """).fetchone()

    # =========================
    # TEACHER ACCOUNT
    # =========================

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (name, username, password, role, branch_id, year_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "Demo Teacher",
        "teacher1",
        "teacher123",
        "teacher",
        cse[0],
        None
    ))

    # =========================
    # CSE STUDENT ACCOUNT
    # =========================

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (name, username, password, role, branch_id, year_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "CSE Students",
        "cse",
        "cse123",
        "student",
        cse[0],
        second_year[0]
    ))

    # =========================
    # CIVIL STUDENT ACCOUNT
    # =========================

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (name, username, password, role, branch_id, year_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "Civil Students",
        "civil",
        "civil123",
        "student",
        civil[0],
        second_year[0]
    ))

    connection.commit()
    connection.close()

    print("================================")
    print("Test Users Created Successfully!")
    print("================================")
    print()
    print("Teacher:")
    print("Username: teacher1")
    print("Password: teacher123")
    print()
    print("CSE Student:")
    print("Username: cse")
    print("Password: cse123")
    print()
    print("Civil Student:")
    print("Username: civil")
    print("Password: civil123")
    print()


if __name__ == "__main__":
    create_users()