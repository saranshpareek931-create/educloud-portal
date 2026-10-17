from flask import Flask, render_template, request, redirect, session, send_from_directory, url_for
import sqlite3
import os
import time
import qrcode
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

# ==================================================
# APP CONFIGURATION
# ==================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")
# ==================================================
# LOGIN SECURITY
# ==================================================

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 5 * 60

login_attempts = {}
DATABASE = "educloud.db"
UPLOAD_FOLDER = "uploads"
QR_FOLDER = "static/qr_codes"

ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)


# ==================================================
# DATABASE
# ==================================================

def get_db():

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    return connection


# ==================================================
# PASSWORD SECURITY
# ==================================================

def is_password_hashed(password):

    if not password:
        return False

    return (
        password.startswith("pbkdf2:")
        or password.startswith("scrypt:")
    )


def verify_password(stored_password, entered_password):

    if not stored_password or not entered_password:
        return False

    # New secure hashed password
    if is_password_hashed(stored_password):

        try:
            return check_password_hash(
                stored_password,
                entered_password
            )
        except ValueError:
            return False

    # Old plaintext password
    return stored_password == entered_password


def migrate_password_if_needed(
    user_id,
    stored_password,
    entered_password
):

    # Already hashed
    if is_password_hashed(stored_password):
        return

    # Old plaintext password matched.
    # Convert it to a secure hash.
    if stored_password == entered_password:

        connection = get_db()

        new_password_hash = generate_password_hash(
            entered_password
        )

        connection.execute("""
            UPDATE users
            SET password = ?
            WHERE id = ?
        """, (
            new_password_hash,
            user_id
        ))

        connection.commit()
        connection.close()


# ==================================================
# FILE CHECK
# ==================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==================================================
# AUTOMATIC QR GENERATOR
# ==================================================

def create_qr(resource_id):

    qr_filename = f"resource_{resource_id}.png"

    qr_path = os.path.join(
        QR_FOLDER,
        qr_filename
    )

    if os.path.exists(qr_path):
        return qr_filename

    resource_url = url_for(
        "view_resource",
        resource_id=resource_id,
        _external=True
    )

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )

    qr.add_data(resource_url)
    qr.make(fit=True)

    qr_image = qr.make_image()
    qr_image.save(qr_path)

    return qr_filename


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")


# ==================================================
# LOGIN PAGE
# ==================================================

@app.route("/login")
def login():

    return render_template("login.html")


# ==================================================
# LOGIN PROCESS - SECURE + LOCKOUT
# ==================================================
@app.route("/login", methods=["POST"])
def login_process():

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    role = request.form.get(
        "role",
        ""
    ).strip()

    if not username or not password or not role:

        return render_template(
            "login.html",
            error="Please enter username, password and account type."
        )

    # ------------------------------------------
    # LOGIN SECURITY KEY
    # ------------------------------------------

    client_ip = request.remote_addr or "unknown"

    login_key = (
        f"{client_ip}:{username.lower()}:{role.lower()}"
    )

    current_time = time.time()

    # ------------------------------------------
    # CHECK EXISTING LOCKOUT
    # ------------------------------------------

    attempt_data = login_attempts.get(login_key)

    if attempt_data:

        failed_attempts = attempt_data["attempts"]

        first_attempt_time = attempt_data["first_attempt"]

        elapsed_time = (
            current_time - first_attempt_time
        )

        # --------------------------------------
        # LOCKOUT STILL ACTIVE
        # --------------------------------------

        if (
            failed_attempts >= MAX_LOGIN_ATTEMPTS
            and elapsed_time < LOGIN_LOCKOUT_SECONDS
        ):

            remaining_seconds = max(
                0,
                int(
                    LOGIN_LOCKOUT_SECONDS
                    - elapsed_time
                )
            )

            remaining_minutes = max(
                1,
                (remaining_seconds + 59) // 60
            )

            return render_template(
                "login.html",
                error=(
                    "Account temporarily locked due to "
                    "too many failed login attempts. "
                    f"Please try again in "
                    f"{remaining_minutes} minute(s)."
                ),
                lockout_remaining=remaining_seconds
            )

        # --------------------------------------
        # LOCKOUT EXPIRED
        # --------------------------------------

        if elapsed_time >= LOGIN_LOCKOUT_SECONDS:

            login_attempts.pop(
                login_key,
                None
            )

            attempt_data = None

    # ------------------------------------------
    # DATABASE USER LOOKUP
    # ------------------------------------------

    connection = get_db()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE username = ?
        AND role = ?
    """, (
        username,
        role
    )).fetchone()

    connection.close()

    # ------------------------------------------
    # INVALID USER
    # ------------------------------------------

    if not user:

        if not attempt_data:

            login_attempts[login_key] = {
                "attempts": 1,
                "first_attempt": current_time
            }

        else:

            attempt_data["attempts"] += 1

        current_attempts = login_attempts[
            login_key
        ]["attempts"]

        # Lock immediately after 5th failed attempt
        if current_attempts >= MAX_LOGIN_ATTEMPTS:

            return render_template(
                "login.html",
                error=(
                    "Too many failed login attempts. "
                    "Your account is locked for 5 minutes."
                ),
                lockout_remaining=LOGIN_LOCKOUT_SECONDS
            )

        return render_template(
            "login.html",
            error="Invalid username, password or account type."
        )

    # ------------------------------------------
    # VERIFY PASSWORD
    # ------------------------------------------

    password_valid = verify_password(
        user["password"],
        password
    )

    # ------------------------------------------
    # INVALID PASSWORD
    # ------------------------------------------

    if not password_valid:

        if not attempt_data:

            login_attempts[login_key] = {
                "attempts": 1,
                "first_attempt": current_time
            }

        else:

            attempt_data["attempts"] += 1

        current_attempts = login_attempts[
            login_key
        ]["attempts"]

        # --------------------------------------
        # 5TH FAILED ATTEMPT
        # --------------------------------------

        if current_attempts >= MAX_LOGIN_ATTEMPTS:

            return render_template(
                "login.html",
                error=(
                    "Too many failed login attempts. "
                    "Your account is locked for 5 minutes."
                ),
                lockout_remaining=LOGIN_LOCKOUT_SECONDS
            )

        return render_template(
            "login.html",
            error="Invalid username, password or account type."
        )

    # ------------------------------------------
    # SUCCESSFUL LOGIN
    # ------------------------------------------

    login_attempts.pop(
        login_key,
        None
    )

    # Automatically convert old plaintext
    # password into secure password hash.

    migrate_password_if_needed(
        user["id"],
        user["password"],
        password
    )

    # ------------------------------------------
    # CLEAR OLD SESSION
    # ------------------------------------------

    session.clear()

    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]
    session["branch_id"] = user["branch_id"]
    session["year_id"] = user["year_id"]

    # ------------------------------------------
    # ROLE REDIRECT
    # ------------------------------------------

    if role == "admin":

        return redirect("/admin")

    if role == "teacher":

        return redirect("/teacher")

    if role == "student":

        return redirect("/student")

    return redirect("/login")



# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    # USER SEARCH/FILTER
    search = request.args.get("search", "").strip()
    branch_filter = request.args.get("branch", "").strip()

    # RESOURCE SEARCH/FILTER
    resource_search = request.args.get(
        "resource_search",
        ""
    ).strip()

    resource_branch = request.args.get(
        "resource_branch",
        ""
    ).strip()

    resource_year = request.args.get(
        "resource_year",
        ""
    ).strip()

    connection = get_db()

    # ------------------------------------------
    # BRANCHES
    # ------------------------------------------

    branches = connection.execute("""
        SELECT *
        FROM branches
        ORDER BY name
    """).fetchall()

    # ------------------------------------------
    # YEARS
    # ------------------------------------------

    years = connection.execute("""
        SELECT *
        FROM years
        ORDER BY id
    """).fetchall()

    # ------------------------------------------
    # TEACHERS
    # ------------------------------------------

    teacher_query = """
        SELECT
            users.id,
            users.name,
            users.username,
            branches.name AS branch_name,
            users.branch_id

        FROM users

        LEFT JOIN branches
            ON users.branch_id = branches.id

        WHERE users.role = 'teacher'
    """

    teacher_params = []

    if search:

        teacher_query += """
            AND (
                users.name LIKE ?
                OR users.username LIKE ?
            )
        """

        search_value = f"%{search}%"

        teacher_params.append(search_value)
        teacher_params.append(search_value)

    if branch_filter:

        teacher_query += """
            AND users.branch_id = ?
        """

        teacher_params.append(branch_filter)

    teacher_query += """
        ORDER BY users.id DESC
    """

    teachers = connection.execute(
        teacher_query,
        teacher_params
    ).fetchall()

    # ------------------------------------------
    # STUDENTS
    # ------------------------------------------

    student_query = """
        SELECT
            users.id,
            users.name,
            users.username,
            users.branch_id,
            users.year_id,
            branches.name AS branch_name,
            years.name AS year_name

        FROM users

        LEFT JOIN branches
            ON users.branch_id = branches.id

        LEFT JOIN years
            ON users.year_id = years.id

        WHERE users.role = 'student'
    """

    student_params = []

    if search:

        student_query += """
            AND (
                users.name LIKE ?
                OR users.username LIKE ?
            )
        """

        search_value = f"%{search}%"

        student_params.append(search_value)
        student_params.append(search_value)

    if branch_filter:

        student_query += """
            AND users.branch_id = ?
        """

        student_params.append(branch_filter)

    student_query += """
        ORDER BY users.id DESC
    """

    students = connection.execute(
        student_query,
        student_params
    ).fetchall()

    # ------------------------------------------
    # ADMIN RESOURCE MANAGEMENT
    # ------------------------------------------

    resource_query = """
        SELECT
            resources.id,
            resources.title,
            resources.description,
            resources.filename,
            resources.created_at,

            resources.branch_id,
            resources.year_id,
            resources.subject_id,
            resources.uploaded_by,

            branches.name AS branch_name,
            years.name AS year_name,
            subjects.name AS subject_name,
            users.name AS teacher_name,
            users.username AS teacher_username

        FROM resources

        LEFT JOIN branches
            ON resources.branch_id = branches.id

        LEFT JOIN years
            ON resources.year_id = years.id

        LEFT JOIN subjects
            ON resources.subject_id = subjects.id

        LEFT JOIN users
            ON resources.uploaded_by = users.id

        WHERE 1 = 1
    """

    resource_params = []

    if resource_search:

        resource_query += """
            AND (
                resources.title LIKE ?
                OR resources.description LIKE ?
                OR subjects.name LIKE ?
                OR users.name LIKE ?
            )
        """

        resource_value = f"%{resource_search}%"

        resource_params.extend([
            resource_value,
            resource_value,
            resource_value,
            resource_value
        ])

    if resource_branch:

        resource_query += """
            AND resources.branch_id = ?
        """

        resource_params.append(resource_branch)

    if resource_year:

        resource_query += """
            AND resources.year_id = ?
        """

        resource_params.append(resource_year)

    resource_query += """
        ORDER BY resources.id DESC
    """

    resources = connection.execute(
        resource_query,
        resource_params
    ).fetchall()

    # ------------------------------------------
    # COUNTS
    # ------------------------------------------

    teacher_count = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE role = 'teacher'
    """).fetchone()["count"]

    student_count = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE role = 'student'
    """).fetchone()["count"]

    resource_count = connection.execute("""
        SELECT COUNT(*) AS count
        FROM resources
    """).fetchone()["count"]

    connection.close()

    return render_template(
        "admin.html",

        name=session["name"],

        teachers=teachers,
        students=students,
        resources=resources,

        branches=branches,
        years=years,

        teacher_count=teacher_count,
        student_count=student_count,
        resource_count=resource_count,

        search=search,
        branch_filter=branch_filter,

        resource_search=resource_search,
        resource_branch=resource_branch,
        resource_year=resource_year
    )


# ==================================================
# ADD TEACHER - ADMIN ONLY
# ==================================================

@app.route("/admin/add-teacher", methods=["GET", "POST"])
def add_teacher():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    branches = connection.execute("""
        SELECT *
        FROM branches
        ORDER BY name
    """).fetchall()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        branch_id = request.form.get("branch_id")

        if (
            not name
            or not username
            or not password
            or not branch_id
        ):

            connection.close()

            return render_template(
                "add_teacher.html",
                name=session["name"],
                branches=branches,
                error="Please fill all fields."
            )

        existing_user = connection.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "add_teacher.html",
                name=session["name"],
                branches=branches,
                error="Username already exists. Please choose another username."
            )

        branch = connection.execute("""
            SELECT *
            FROM branches
            WHERE id = ?
        """, (
            branch_id,
        )).fetchone()

        if not branch:

            connection.close()

            return render_template(
                "add_teacher.html",
                name=session["name"],
                branches=branches,
                error="Invalid branch selected."
            )

        # HASH PASSWORD BEFORE DATABASE INSERT
        password_hash = generate_password_hash(
            password
        )

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
            password_hash,
            branch_id
        ))

        connection.commit()
        connection.close()

        return redirect("/admin")

    connection.close()

    return render_template(
        "add_teacher.html",
        name=session["name"],
        branches=branches
    )


# ==================================================
# EDIT TEACHER
# ==================================================

@app.route(
    "/admin/edit-teacher/<int:teacher_id>",
    methods=["GET", "POST"]
)
def edit_teacher(teacher_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    teacher = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
        AND role = 'teacher'
    """, (
        teacher_id,
    )).fetchone()

    if not teacher:

        connection.close()
        return redirect("/admin")

    branches = connection.execute("""
        SELECT *
        FROM branches
        ORDER BY name
    """).fetchall()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        branch_id = request.form.get(
            "branch_id"
        )

        if not name or not username or not branch_id:

            connection.close()

            return render_template(
                "edit_teacher.html",
                teacher=teacher,
                branches=branches,
                error="Name, username and branch are required."
            )

        existing_user = connection.execute("""
            SELECT id
            FROM users
            WHERE username = ?
            AND id != ?
        """, (
            username,
            teacher_id
        )).fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "edit_teacher.html",
                teacher=teacher,
                branches=branches,
                error="Username already exists."
            )

        branch = connection.execute("""
            SELECT *
            FROM branches
            WHERE id = ?
        """, (
            branch_id,
        )).fetchone()

        if not branch:

            connection.close()

            return render_template(
                "edit_teacher.html",
                teacher=teacher,
                branches=branches,
                error="Invalid branch selected."
            )

        if password:

            password_hash = generate_password_hash(
                password
            )

            connection.execute("""
                UPDATE users
                SET
                    name = ?,
                    username = ?,
                    password = ?,
                    branch_id = ?
                WHERE id = ?
                AND role = 'teacher'
            """, (
                name,
                username,
                password_hash,
                branch_id,
                teacher_id
            ))

        else:

            connection.execute("""
                UPDATE users
                SET
                    name = ?,
                    username = ?,
                    branch_id = ?
                WHERE id = ?
                AND role = 'teacher'
            """, (
                name,
                username,
                branch_id,
                teacher_id
            ))

        connection.commit()
        connection.close()

        return redirect("/admin")

    connection.close()

    return render_template(
        "edit_teacher.html",
        teacher=teacher,
        branches=branches
    )


# ==================================================
# DELETE TEACHER
# ==================================================

@app.route(
    "/admin/delete-teacher/<int:teacher_id>",
    methods=["POST"]
)
def delete_teacher(teacher_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    teacher = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
        AND role = 'teacher'
    """, (
        teacher_id,
    )).fetchone()

    if not teacher:

        connection.close()
        return redirect("/admin")

    connection.execute("""
        DELETE FROM users
        WHERE id = ?
        AND role = 'teacher'
    """, (
        teacher_id,
    ))

    connection.commit()
    connection.close()

    return redirect("/admin")


# ==================================================
# ADD STUDENT - ADMIN ONLY
# ==================================================

@app.route("/admin/add-student", methods=["GET", "POST"])
def add_student():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    branches = connection.execute("""
        SELECT *
        FROM branches
        ORDER BY name
    """).fetchall()

    years = connection.execute("""
        SELECT *
        FROM years
        ORDER BY id
    """).fetchall()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        branch_id = request.form.get(
            "branch_id"
        )

        year_id = request.form.get(
            "year_id"
        )

        if (
            not name
            or not username
            or not password
            or not branch_id
            or not year_id
        ):

            connection.close()

            return render_template(
                "add_student.html",
                name=session["name"],
                branches=branches,
                years=years,
                error="Please fill all fields."
            )

        existing_user = connection.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "add_student.html",
                name=session["name"],
                branches=branches,
                years=years,
                error="Username already exists. Please choose another username."
            )

        branch = connection.execute("""
            SELECT *
            FROM branches
            WHERE id = ?
        """, (
            branch_id,
        )).fetchone()

        year = connection.execute("""
            SELECT *
            FROM years
            WHERE id = ?
        """, (
            year_id,
        )).fetchone()

        if not branch or not year:

            connection.close()

            return render_template(
                "add_student.html",
                name=session["name"],
                branches=branches,
                years=years,
                error="Invalid branch or year selected."
            )

        # HASH PASSWORD BEFORE DATABASE INSERT
        password_hash = generate_password_hash(
            password
        )

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
            VALUES (?, ?, ?, 'student', ?, ?)
        """, (
            name,
            username,
            password_hash,
            branch_id,
            year_id
        ))

        connection.commit()
        connection.close()

        return redirect("/admin")

    connection.close()

    return render_template(
        "add_student.html",
        name=session["name"],
        branches=branches,
        years=years
    )


# ==================================================
# EDIT STUDENT
# ==================================================

@app.route(
    "/admin/edit-student/<int:student_id>",
    methods=["GET", "POST"]
)
def edit_student(student_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    student = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
        AND role = 'student'
    """, (
        student_id,
    )).fetchone()

    if not student:

        connection.close()
        return redirect("/admin")

    branches = connection.execute("""
        SELECT *
        FROM branches
        ORDER BY name
    """).fetchall()

    years = connection.execute("""
        SELECT *
        FROM years
        ORDER BY id
    """).fetchall()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        branch_id = request.form.get(
            "branch_id"
        )

        year_id = request.form.get(
            "year_id"
        )

        if (
            not name
            or not username
            or not branch_id
            or not year_id
        ):

            connection.close()

            return render_template(
                "edit_student.html",
                student=student,
                branches=branches,
                years=years,
                error="Name, username, branch and year are required."
            )

        existing_user = connection.execute("""
            SELECT id
            FROM users
            WHERE username = ?
            AND id != ?
        """, (
            username,
            student_id
        )).fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "edit_student.html",
                student=student,
                branches=branches,
                years=years,
                error="Username already exists."
            )

        branch = connection.execute("""
            SELECT *
            FROM branches
            WHERE id = ?
        """, (
            branch_id,
        )).fetchone()

        year = connection.execute("""
            SELECT *
            FROM years
            WHERE id = ?
        """, (
            year_id,
        )).fetchone()

        if not branch or not year:

            connection.close()

            return render_template(
                "edit_student.html",
                student=student,
                branches=branches,
                years=years,
                error="Invalid branch or year selected."
            )

        if password:

            password_hash = generate_password_hash(
                password
            )

            connection.execute("""
                UPDATE users
                SET
                    name = ?,
                    username = ?,
                    password = ?,
                    branch_id = ?,
                    year_id = ?
                WHERE id = ?
                AND role = 'student'
            """, (
                name,
                username,
                password_hash,
                branch_id,
                year_id,
                student_id
            ))

        else:

            connection.execute("""
                UPDATE users
                SET
                    name = ?,
                    username = ?,
                    branch_id = ?,
                    year_id = ?
                WHERE id = ?
                AND role = 'student'
            """, (
                name,
                username,
                branch_id,
                year_id,
                student_id
            ))

        connection.commit()
        connection.close()

        return redirect("/admin")

    connection.close()

    return render_template(
        "edit_student.html",
        student=student,
        branches=branches,
        years=years
    )


# ==================================================
# DELETE STUDENT
# ==================================================

@app.route(
    "/admin/delete-student/<int:student_id>",
    methods=["POST"]
)
def delete_student(student_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    student = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
        AND role = 'student'
    """, (
        student_id,
    )).fetchone()

    if not student:

        connection.close()
        return redirect("/admin")

    connection.execute("""
        DELETE FROM users
        WHERE id = ?
        AND role = 'student'
    """, (
        student_id,
    ))

    connection.commit()
    connection.close()

    return redirect("/admin")


# ==================================================
# ADMIN DELETE RESOURCE
# ==================================================

@app.route(
    "/admin/delete-resource/<int:resource_id>",
    methods=["POST"]
)
def admin_delete_resource(resource_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    resource = connection.execute("""
        SELECT *
        FROM resources
        WHERE id = ?
    """, (
        resource_id,
    )).fetchone()

    if not resource:

        connection.close()
        return redirect("/admin")

    filename = resource["filename"]

    connection.execute("""
        DELETE FROM resources
        WHERE id = ?
    """, (
        resource_id,
    ))

    connection.commit()
    connection.close()

    # DELETE FILE
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    # DELETE QR
    qr_path = os.path.join(
        QR_FOLDER,
        f"resource_{resource_id}.png"
    )

    if os.path.exists(qr_path):
        os.remove(qr_path)

    return redirect("/admin")


# ==================================================
# TEACHER DASHBOARD
# ==================================================

@app.route("/teacher")
def teacher_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "teacher":
        return redirect("/login")

    connection = get_db()

    branch = None

    if session["branch_id"]:

        branch = connection.execute("""
            SELECT *
            FROM branches
            WHERE id = ?
        """, (
            session["branch_id"],
        )).fetchone()

    years = connection.execute("""
        SELECT *
        FROM years
        ORDER BY id
    """).fetchall()

    resources = connection.execute("""
        SELECT
            resources.*,
            subjects.name AS subject_name,
            years.name AS year_name

        FROM resources

        JOIN subjects
            ON resources.subject_id = subjects.id

        JOIN years
            ON resources.year_id = years.id

        WHERE resources.uploaded_by = ?

        ORDER BY resources.created_at DESC
    """, (
        session["user_id"],
    )).fetchall()

    connection.close()

    return render_template(
        "teacher.html",
        name=session["name"],
        branch=branch,
        years=years,
        resources=resources
    )


# ==================================================
# GET SUBJECTS
# ==================================================

@app.route("/get-subjects/<int:year_id>")
def get_subjects(year_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "teacher":
        return redirect("/login")

    connection = get_db()

    subjects = connection.execute("""
        SELECT *
        FROM subjects
        WHERE branch_id = ?
        AND year_id = ?
        ORDER BY name
    """, (
        session["branch_id"],
        year_id
    )).fetchall()

    connection.close()

    return {
        "subjects": [
            {
                "id": subject["id"],
                "name": subject["name"]
            }
            for subject in subjects
        ]
    }


# ==================================================
# UPLOAD RESOURCE
# ==================================================

@app.route(
    "/upload-resource",
    methods=["POST"]
)
def upload_resource():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "teacher":
        return redirect("/login")

    title = request.form.get("title")
    description = request.form.get("description")
    year_id = request.form.get("year_id")
    subject_id = request.form.get("subject_id")

    file = request.files.get("file")

    if not title or not year_id or not subject_id:
        return redirect("/teacher")

    if not file or file.filename == "":
        return redirect("/teacher")

    if not allowed_file(file.filename):
        return redirect("/teacher")

    filename = secure_filename(
        file.filename
    )

    name, extension = os.path.splitext(
        filename
    )

    counter = 1

    while os.path.exists(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    ):

        filename = (
            f"{name}_{counter}{extension}"
        )

        counter += 1

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(file_path)

    connection = get_db()

    subject = connection.execute("""
        SELECT *
        FROM subjects
        WHERE id = ?
        AND branch_id = ?
        AND year_id = ?
    """, (
        subject_id,
        session["branch_id"],
        year_id
    )).fetchone()

    if not subject:

        connection.close()

        if os.path.exists(file_path):
            os.remove(file_path)

        return redirect("/teacher")

    cursor = connection.execute("""
        INSERT INTO resources
        (
            title,
            description,
            filename,
            branch_id,
            year_id,
            subject_id,
            uploaded_by
        )

        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        description,
        filename,
        session["branch_id"],
        year_id,
        subject_id,
        session["user_id"]
    ))

    connection.commit()

    resource_id = cursor.lastrowid

    connection.close()

    create_qr(resource_id)

    return redirect("/teacher")


# ==================================================
# STUDENT DASHBOARD
# ==================================================

@app.route("/student")
def student_dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "student":
        return redirect("/login")

    connection = get_db()

    branch = connection.execute("""
        SELECT *
        FROM branches
        WHERE id = ?
    """, (
        session["branch_id"],
    )).fetchone()

    year = connection.execute("""
        SELECT *
        FROM years
        WHERE id = ?
    """, (
        session["year_id"],
    )).fetchone()

    resources = connection.execute("""
        SELECT
            resources.*,
            subjects.name AS subject_name,
            years.name AS year_name

        FROM resources

        JOIN subjects
            ON resources.subject_id = subjects.id

        JOIN years
            ON resources.year_id = years.id

        WHERE resources.branch_id = ?
        AND resources.year_id = ?

        ORDER BY
            subjects.name,
            resources.created_at DESC
    """, (
        session["branch_id"],
        session["year_id"]
    )).fetchall()

    connection.close()

    for resource in resources:
        create_qr(resource["id"])

    return render_template(
        "student.html",
        name=session["name"],
        branch=branch,
        year=year,
        resources=resources
    )


# ==================================================
# SECURE RESOURCE PAGE
# ==================================================

@app.route(
    "/resource/<int:resource_id>"
)
def view_resource(resource_id):

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db()

    resource = connection.execute("""
        SELECT
            resources.*,
            subjects.name AS subject_name,
            years.name AS year_name,
            branches.name AS branch_name

        FROM resources

        JOIN subjects
            ON resources.subject_id = subjects.id

        JOIN years
            ON resources.year_id = years.id

        JOIN branches
            ON resources.branch_id = branches.id

        WHERE resources.id = ?
    """, (
        resource_id,
    )).fetchone()

    connection.close()

    if not resource:
        return "Resource not found", 404

    if session["role"] == "student":

        if resource["branch_id"] != session["branch_id"]:
            return "Access denied", 403

        if resource["year_id"] != session["year_id"]:
            return "Access denied", 403

    return render_template(
        "resource.html",
        resource=resource
    )


# ==================================================
# DOWNLOAD RESOURCE
# ==================================================

@app.route(
    "/download/<int:resource_id>"
)
def download_resource(resource_id):

    if "user_id" not in session:
        return redirect("/login")

    connection = get_db()

    resource = connection.execute("""
        SELECT *
        FROM resources
        WHERE id = ?
    """, (
        resource_id,
    )).fetchone()

    connection.close()

    if not resource:
        return "Resource not found", 404

    if session["role"] == "student":

        if resource["branch_id"] != session["branch_id"]:
            return "Access denied", 403

        if resource["year_id"] != session["year_id"]:
            return "Access denied", 403

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        resource["filename"]
    )

    if not os.path.exists(file_path):
        return "File not found on server", 404

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        resource["filename"],
        as_attachment=True
    )


# ==================================================
# DELETE RESOURCE - TEACHER
# ==================================================

@app.route(
    "/delete-resource/<int:resource_id>",
    methods=["POST"]
)
def delete_resource(resource_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "teacher":
        return redirect("/login")

    connection = get_db()

    resource = connection.execute("""
        SELECT *
        FROM resources
        WHERE id = ?
        AND uploaded_by = ?
    """, (
        resource_id,
        session["user_id"]
    )).fetchone()

    if not resource:

        connection.close()
        return redirect("/teacher")

    filename = resource["filename"]

    connection.execute("""
        DELETE FROM resources
        WHERE id = ?
        AND uploaded_by = ?
    """, (
        resource_id,
        session["user_id"]
    ))

    connection.commit()
    connection.close()

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    qr_path = os.path.join(
        QR_FOLDER,
        f"resource_{resource_id}.png"
    )

    if os.path.exists(qr_path):
        os.remove(qr_path)

    return redirect("/teacher")


# ==================================================
# EDIT RESOURCE
# ==================================================

@app.route(
    "/edit-resource/<int:resource_id>",
    methods=["GET", "POST"]
)
def edit_resource(resource_id):

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "teacher":
        return redirect("/login")

    connection = get_db()

    resource = connection.execute("""
        SELECT *
        FROM resources
        WHERE id = ?
        AND uploaded_by = ?
    """, (
        resource_id,
        session["user_id"]
    )).fetchone()

    if not resource:

        connection.close()
        return redirect("/teacher")

    if request.method == "POST":

        title = request.form.get("title")
        description = request.form.get("description")
        year_id = request.form.get("year_id")
        subject_id = request.form.get("subject_id")

        if not title or not year_id or not subject_id:

            connection.close()

            return redirect(
                url_for(
                    "edit_resource",
                    resource_id=resource_id
                )
            )

        subject = connection.execute("""
            SELECT *
            FROM subjects
            WHERE id = ?
            AND branch_id = ?
            AND year_id = ?
        """, (
            subject_id,
            session["branch_id"],
            year_id
        )).fetchone()

        if not subject:

            connection.close()

            return redirect(
                url_for(
                    "edit_resource",
                    resource_id=resource_id
                )
            )

        connection.execute("""
            UPDATE resources

            SET
                title = ?,
                description = ?,
                year_id = ?,
                subject_id = ?

            WHERE id = ?
            AND uploaded_by = ?
        """, (
            title,
            description,
            year_id,
            subject_id,
            resource_id,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        return redirect("/teacher")

    years = connection.execute("""
        SELECT *
        FROM years
        ORDER BY id
    """).fetchall()

    subjects = connection.execute("""
        SELECT *
        FROM subjects
        WHERE branch_id = ?
        AND year_id = ?
        ORDER BY name
    """, (
        session["branch_id"],
        resource["year_id"]
    )).fetchall()

    connection.close()

    return render_template(
        "edit_resource.html",
        resource=resource,
        years=years,
        subjects=subjects
    )


# ==================================================
# ADMIN ANALYTICS
# ==================================================

@app.route("/admin/analytics")
def admin_analytics():

    if "user_id" not in session:
        return redirect("/login")

    if session["role"] != "admin":
        return redirect("/login")

    connection = get_db()

    # =========================
    # OVERALL COUNTS
    # =========================

    total_students = connection.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE role = 'student'
    """).fetchone()[0]

    total_teachers = connection.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE role = 'teacher'
    """).fetchone()[0]

    total_resources = connection.execute("""
        SELECT COUNT(*)
        FROM resources
    """).fetchone()[0]

    total_branches = connection.execute("""
        SELECT COUNT(*)
        FROM branches
    """).fetchone()[0]

    # =========================
    # BRANCH-WISE STATISTICS
    # =========================

    branch_stats = connection.execute("""
        SELECT
            branches.id,
            branches.name,
            branches.code,

            (
                SELECT COUNT(*)
                FROM users
                WHERE users.branch_id = branches.id
                AND users.role = 'student'
            ) AS students,

            (
                SELECT COUNT(*)
                FROM users
                WHERE users.branch_id = branches.id
                AND users.role = 'teacher'
            ) AS teachers,

            (
                SELECT COUNT(*)
                FROM resources
                WHERE resources.branch_id = branches.id
            ) AS resources

        FROM branches

        ORDER BY branches.name
    """).fetchall()

    # =========================
    # YEAR-WISE RESOURCES
    # =========================

    year_stats = connection.execute("""
        SELECT
            years.id,
            years.name,
            COUNT(resources.id) AS resources

        FROM years

        LEFT JOIN resources
            ON resources.year_id = years.id

        GROUP BY years.id, years.name

        ORDER BY years.id
    """).fetchall()

    # =========================
    # CALCULATE BAR PERCENTAGE
    # =========================

    max_year_resources = 0

    for item in year_stats:

        if item["resources"] > max_year_resources:

            max_year_resources = item["resources"]

    year_stats_with_percentage = []

    for item in year_stats:

        if max_year_resources > 0:

            percentage = round(
                (
                    item["resources"]
                    / max_year_resources
                ) * 100,
                1
            )

        else:

            percentage = 0

        row = {
            "id": item["id"],
            "name": item["name"],
            "resources": item["resources"],
            "percentage": percentage
        }

        year_stats_with_percentage.append(
            row
        )

    # =========================
    # SUBJECT-WISE RESOURCES
    # =========================

    subject_stats = connection.execute("""
        SELECT
            subjects.name,
            branches.name AS branch_name,
            COUNT(resources.id) AS resources

        FROM subjects

        JOIN branches
            ON subjects.branch_id = branches.id

        LEFT JOIN resources
            ON resources.subject_id = subjects.id

        GROUP BY
            subjects.id,
            subjects.name,
            branches.name

        ORDER BY resources DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin_analytics.html",

        total_students=total_students,
        total_teachers=total_teachers,
        total_resources=total_resources,
        total_branches=total_branches,

        branch_stats=branch_stats,

        year_stats=year_stats_with_percentage,

        subject_stats=subject_stats
    )


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(debug=True)