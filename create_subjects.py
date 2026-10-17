import sqlite3

DATABASE = "educloud.db"


def create_subjects():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # =========================
    # GET BRANCH IDs
    # =========================

    branches = {}

    rows = cursor.execute("""
        SELECT id, code
        FROM branches
    """).fetchall()

    for row in rows:
        branches[row[1]] = row[0]


    # =========================
    # GET YEAR IDs
    # =========================

    years = {}

    rows = cursor.execute("""
        SELECT id, name
        FROM years
    """).fetchall()

    for row in rows:
        years[row[1]] = row[0]


    # =========================
    # CSE SUBJECTS
    # =========================

    cse_subjects = {
        "1st Year": [
            "Programming in C",
            "Computer Fundamentals",
            "Mathematics",
            "Communication Skills",
            "Engineering Physics"
        ],

        "2nd Year": [
            "Data Structures",
            "Database Management System",
            "Operating System",
            "Computer Networks",
            "Web Development"
        ],

        "3rd Year": [
            "Software Engineering",
            "Python Programming",
            "Artificial Intelligence",
            "Cyber Security",
            "Cloud Computing"
        ]
    }


    # =========================
    # CIVIL SUBJECTS
    # =========================

    civil_subjects = {
        "1st Year": [
            "Engineering Mathematics",
            "Engineering Physics",
            "Engineering Chemistry",
            "Communication Skills",
            "Engineering Drawing"
        ],

        "2nd Year": [
            "Strength of Materials",
            "Surveying",
            "Building Materials",
            "Fluid Mechanics",
            "Concrete Technology"
        ],

        "3rd Year": [
            "Structural Engineering",
            "Transportation Engineering",
            "Environmental Engineering",
            "Geotechnical Engineering",
            "Estimation and Costing"
        ]
    }


    # =========================
    # MECHANICAL SUBJECTS
    # =========================

    mech_subjects = {
        "1st Year": [
            "Engineering Mathematics",
            "Engineering Physics",
            "Engineering Chemistry",
            "Engineering Drawing",
            "Workshop Practice"
        ],

        "2nd Year": [
            "Thermodynamics",
            "Fluid Mechanics",
            "Manufacturing Processes",
            "Theory of Machines",
            "Material Science"
        ],

        "3rd Year": [
            "Heat Transfer",
            "Machine Design",
            "Automobile Engineering",
            "Industrial Engineering",
            "Production Management"
        ]
    }


    # =========================
    # ELECTRICAL SUBJECTS
    # =========================

    ee_subjects = {
        "1st Year": [
            "Engineering Mathematics",
            "Engineering Physics",
            "Engineering Chemistry",
            "Communication Skills",
            "Engineering Drawing"
        ],

        "2nd Year": [
            "Electrical Machines",
            "Network Theory",
            "Digital Electronics",
            "Electrical Measurements",
            "Power Systems"
        ],

        "3rd Year": [
            "Power Electronics",
            "Control Systems",
            "Microprocessors",
            "Industrial Electronics",
            "Electrical Drives"
        ]
    }


    all_subjects = {
        "CSE": cse_subjects,
        "CIVIL": civil_subjects,
        "MECH": mech_subjects,
        "EE": ee_subjects
    }


    # =========================
    # INSERT SUBJECTS
    # =========================

    for branch_code, branch_subjects in all_subjects.items():

        branch_id = branches.get(branch_code)

        if not branch_id:
            continue

        for year_name, subjects in branch_subjects.items():

            year_id = years.get(year_name)

            if not year_id:
                continue

            for subject_name in subjects:

                cursor.execute("""
                    SELECT id
                    FROM subjects
                    WHERE name = ?
                    AND branch_id = ?
                    AND year_id = ?
                """, (
                    subject_name,
                    branch_id,
                    year_id
                ))

                existing = cursor.fetchone()

                if not existing:

                    cursor.execute("""
                        INSERT INTO subjects
                        (name, branch_id, year_id)
                        VALUES (?, ?, ?)
                    """, (
                        subject_name,
                        branch_id,
                        year_id
                    ))


    connection.commit()
    connection.close()

    print("================================")
    print("Subjects Created Successfully!")
    print("================================")


if __name__ == "__main__":
    create_subjects()