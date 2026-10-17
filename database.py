import sqlite3


DATABASE = "educloud.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():

    connection = get_connection()
    cursor = connection.cursor()

    # =========================
    # BRANCHES
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE
        )
    """)


    # =========================
    # YEARS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)


    # =========================
    # USERS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            username TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL,

            role TEXT NOT NULL,

            branch_id INTEGER,

            year_id INTEGER,

            FOREIGN KEY (branch_id)
                REFERENCES branches(id),

            FOREIGN KEY (year_id)
                REFERENCES years(id)
        )
    """)


    # =========================
    # SUBJECTS
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            branch_id INTEGER NOT NULL,

            year_id INTEGER NOT NULL,

            FOREIGN KEY (branch_id)
                REFERENCES branches(id),

            FOREIGN KEY (year_id)
                REFERENCES years(id)
        )
    """)


    # =========================
    # RESOURCES
    # =========================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            description TEXT,

            filename TEXT NOT NULL,

            branch_id INTEGER NOT NULL,

            year_id INTEGER NOT NULL,

            subject_id INTEGER NOT NULL,

            uploaded_by INTEGER NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (branch_id)
                REFERENCES branches(id),

            FOREIGN KEY (year_id)
                REFERENCES years(id),

            FOREIGN KEY (subject_id)
                REFERENCES subjects(id),

            FOREIGN KEY (uploaded_by)
                REFERENCES users(id)
        )
    """)


    # =========================
    # DEFAULT BRANCHES
    # =========================

    branches = [
        ("Computer Engineering", "CSE"),
        ("Civil Engineering", "CIVIL"),
        ("Mechanical Engineering", "MECH"),
        ("Electrical Engineering", "EE")
    ]

    for name, code in branches:

        cursor.execute("""
            INSERT OR IGNORE INTO branches (name, code)
            VALUES (?, ?)
        """, (name, code))


    # =========================
    # DEFAULT YEARS
    # =========================

    years = [
        "1st Year",
        "2nd Year",
        "3rd Year"
    ]

    for year in years:

        cursor.execute("""
            INSERT OR IGNORE INTO years (name)
            VALUES (?)
        """, (year,))


    connection.commit()

    connection.close()


if __name__ == "__main__":
    create_database()

    print("================================")
    print("EduCloud Database Created!")
    print("================================")