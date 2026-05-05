from flask import Flask, render_template, request, redirect, session, send_file, jsonify
from datetime import date, datetime
import io
import os
import psycopg2
import psycopg2.errors
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# ---------------- CONFIG ----------------
app.secret_key = os.environ.get("SECRET_KEY", "fallback_only_for_local_dev")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True


# ---------------- DB ----------------
def get_db_connection():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT,
            password TEXT,
            role TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name TEXT,
            salary INTEGER,
            user_id INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER,
            user_id INTEGER,
            date TEXT,
            status TEXT
        )
    ''')

    conn.commit()

    # Safe column migrations — only catch DuplicateColumn, nothing else
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN check_in TIME")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN check_out TIME")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN check_in_time TIME")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN check_out_time TIME")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

    conn.close()


init_db()


# ---------------- ADMIN SEED ----------------
def create_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=%s", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            ("admin", generate_password_hash("admin123"), "admin")
        )
        conn.commit()
    conn.close()


create_admin()


# ---------------- AUTH HELPERS ----------------
def login_required():
    return 'user_id' not in session


def admin_required():
    return 'user_id' not in session or session.get('role') != 'admin'


# ---------------- AUTH ROUTES ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return "Error: Username and password are required", 400

        conn = get_db_connection()
        cursor = conn.cursor()

        hashed_password = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) RETURNING id",
            (username, hashed_password, "employee")
        )
        user_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO employees (user_id, name, salary) VALUES (%s, %s, %s)",
            (user_id, username, 0)
        )
        conn.commit()
        conn.close()
        return redirect('/login')

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return "Error: Username and password are required", 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['role'] = user[3]
            return redirect('/')
        else:
            return "Invalid credentials", 401

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------- HOME (router only) ----------------
@app.route('/')
def home():
    if login_required():
        return redirect('/login')

    if session.get('role') == 'admin':
        return redirect('/admin/dashboard')
    else:
        return redirect('/employee/dashboard')


# ---------------- ADMIN DASHBOARD ----------------
@app.route('/admin/dashboard')
def admin_dashboard():
    if admin_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    today = date.today().isoformat()

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE status=%s AND date=%s",
        ('present', today)
    )
    present_today = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE status=%s AND date=%s",
        ('absent', today)
    )
    absent_today = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'index.html',
        employees=employees,
        role='admin',
        present_today=present_today,
        absent_today=absent_today
    )


# ---------------- EMPLOYEE DASHBOARD ----------------
@app.route('/employee/dashboard')
def employee_dashboard():
    if login_required():
        return redirect('/login')

    if session.get('role') == 'admin':
        return redirect('/admin/dashboard')

    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE user_id=%s", (user_id,))
    emp = cursor.fetchone()

    if not emp:
        conn.close()
        return "⚠️ No employee profile found. Contact admin.", 404

    month = date.today().strftime("%Y-%m")

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE employee_id=%s AND status=%s AND date LIKE %s",
        (emp[0], 'present', f"{month}%")
    )
    present = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE employee_id=%s AND status=%s AND date LIKE %s",
        (emp[0], 'absent', f"{month}%")
    )
    absent = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "employee_dashboard.html",
        employee=emp,
        present=present,
        absent=absent
    )


# ---------------- ADD EMPLOYEE ----------------
@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if admin_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        salary_raw = request.form.get('salary', '')
        user_id = request.form.get('user_id', '')
        check_in = request.form.get('check_in', '')
        check_out = request.form.get('check_out', '')

        if not name:
            conn.close()
            return "Error: Employee name cannot be empty", 400

        if not salary_raw.isdigit() or int(salary_raw) <= 0:
            conn.close()
            return "Error: Salary must be a positive number", 400

        if not user_id:
            conn.close()
            return "Error: Please select a user", 400

        if not check_in or not check_out:
            conn.close()
            return "Error: Check-in and check-out times are required", 400

        salary = int(salary_raw)

        cursor.execute("""
            INSERT INTO employees (name, salary, user_id, check_in, check_out)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, salary, user_id, check_in, check_out))

        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT id, username FROM users WHERE role='employee'")
    users = cursor.fetchall()
    conn.close()

    return render_template('add_employee.html', users=users)

# ---------------- ATTENDANCE ----------------
@app.route('/attendance/<int:id>', methods=['GET', 'POST'])
def attendance(id):
    if admin_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    if request.method == 'POST':
        status = request.form.get('status', '').strip()
        check_in_time = request.form.get('check_in_time', '').strip()
        check_out_time = request.form.get('check_out_time', '').strip()

        if not status:
            conn.close()
            return "Error: Status is required", 400

        # If present, times are mandatory
        if status == 'present':
            if not check_in_time or not check_out_time:
                conn.close()
                return "Error: Check-in and check-out times are required for present employees", 400
            # validate check_out is after check_in
            fmt = "%H:%M"
            try:
                t_in = datetime.strptime(check_in_time, fmt)
                t_out = datetime.strptime(check_out_time, fmt)
                if t_out <= t_in:
                    conn.close()
                    return "Error: Check-out time must be after check-in time", 400
            except ValueError:
                conn.close()
                return "Error: Invalid time format", 400

        # If absent, ignore any times submitted
        if status == 'absent':
            check_in_time = None
            check_out_time = None

        # Delete existing record for today and reinsert
        cursor.execute(
            "DELETE FROM attendance WHERE employee_id=%s AND date=%s",
            (id, today)
        )
        cursor.execute("""
            INSERT INTO attendance
            (employee_id, user_id, date, status, check_in_time, check_out_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id, session['user_id'], today, status, check_in_time, check_out_time))

        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    cursor.execute(
        "SELECT date, status, check_in_time, check_out_time FROM attendance WHERE employee_id=%s ORDER BY date DESC",
        (id,)
    )
    records = cursor.fetchall()
    conn.close()

    return render_template("attendance.html", employee=emp, records=records, today=today)


# ---------------- CALCULATE SALARY ----------------
GRACE_PERIOD_MINUTES = 15  # adjust this as needed

@app.route('/calculate/<int:id>')
def calculate(id):
    if login_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Use named columns instead of positional index
    cursor.execute("""
        SELECT id, name, salary, user_id, check_in, check_out
        FROM employees WHERE id=%s
    """, (id,))
    emp = cursor.fetchone()

    if not emp:
        conn.close()
        return "Employee not found", 404

    emp_id, emp_name, emp_salary, emp_user_id, expected_in, expected_out = emp

    if not expected_in or not expected_out:
        conn.close()
        return "⚠️ Working hours not set for this employee. Admin must set check-in/check-out in employee profile.", 400

    # Only fetch present days that have both times recorded
    month = date.today().strftime("%Y-%m")

    cursor.execute("""
        SELECT check_in_time, check_out_time
        FROM attendance
        WHERE employee_id=%s
        AND status='present'
        AND date LIKE %s
        AND check_in_time IS NOT NULL
        AND check_out_time IS NOT NULL
    """, (id, f"{month}%"))

    records = cursor.fetchall()
    conn.close()

    if not records:
        return "No attendance data with recorded times found for this month", 404

    fmt = "%H:%M:%S"
    expected_in_dt = datetime.strptime(str(expected_in), fmt)
    expected_out_dt = datetime.strptime(str(expected_out), fmt)

    total_penalty_minutes = 0

    for actual_in, actual_out in records:
        actual_in_dt = datetime.strptime(str(actual_in), fmt)
        actual_out_dt = datetime.strptime(str(actual_out), fmt)

        # Late arrival — only penalise beyond grace period
        late_minutes = (actual_in_dt - expected_in_dt).total_seconds() / 60
        if late_minutes > GRACE_PERIOD_MINUTES:
            total_penalty_minutes += late_minutes

        # Early exit — only penalise beyond grace period
        early_minutes = (expected_out_dt - actual_out_dt).total_seconds() / 60
        if early_minutes > GRACE_PERIOD_MINUTES:
            total_penalty_minutes += early_minutes

    # Salary deduction calculation
    salary = emp_salary
    working_minutes_per_day = 8 * 60
    per_day_salary = salary / 30
    per_minute_salary = per_day_salary / working_minutes_per_day

    # Count only present days with recorded times
    present_days = len(records)

    # What the employee actually earned based on days worked
    earned_salary = per_day_salary * present_days

    # Penalty for late arrival / early exit
    total_deduction = per_minute_salary * total_penalty_minutes

    # Final = what they earned minus penalties
    final_salary = int(earned_salary - total_deduction)
    
    return render_template(
    'result.html',
    name=emp_name,
    total=final_salary,
    penalty=int(total_deduction),
    minutes=int(total_penalty_minutes),
    grace_period=GRACE_PERIOD_MINUTES,
    month=date.today().strftime('%B %Y'),
    earned_salary=int(earned_salary),
    present_days=present_days,
    gross_salary=emp_salary
)

# ---------------- PAYSLIP PDF ----------------
@app.route('/payslip/<int:id>')
def payslip(id):
    if login_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    if not emp:
        conn.close()
        return "Employee not found", 404

    # Employees can only view their own payslip
    if session.get('role') != 'admin' and emp[3] != session.get('user_id'):
        conn.close()
        return "Access denied", 403

    month = date.today().strftime("%Y-%m")

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE employee_id=%s AND status='present' AND date LIKE %s",
        (id, f"{month}%")
    )
    days = cursor.fetchone()[0]
    conn.close()

    total = int((emp[2] / 30) * days)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("Salary Slip", styles['Title']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Name: {emp[1]}", styles['Normal']))
    elements.append(Paragraph(f"Salary: ₹{total}", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="payslip.pdf")



# ---------------- CALENDAR ----------------
@app.route('/calendar/<int:id>')
def calendar_view(id):
    if login_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    employee = cursor.fetchone()

    cursor.execute(
        "SELECT date, status FROM attendance WHERE employee_id=%s",
        (id,)
    )
    records = cursor.fetchall()
    conn.close()

    return render_template('calendar.html', employee=employee, records=records)


# ---------------- EMPLOYEE PROFILE ----------------
@app.route('/employee/<int:id>')
def employee_profile(id):
    if login_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    if not emp:
        conn.close()
        return "Employee not found", 404

    month = date.today().strftime("%Y-%m")

    cursor.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE employee_id=%s AND status='present' AND date LIKE %s
    """, (id, f"{month}%"))
    present = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE employee_id=%s AND status='absent' AND date LIKE %s
    """, (id, f"{month}%"))
    absent = cursor.fetchone()[0]

    cursor.execute("""
        SELECT date, status FROM attendance
        WHERE employee_id=%s ORDER BY date DESC
    """, (id,))
    records = cursor.fetchall()

    conn.close()

    return render_template(
        'employee_profile.html',
        emp=emp,
        present=present,
        absent=absent,
        records=records
    )


# ---------------- DELETE EMPLOYEE ----------------
@app.route('/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    if admin_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM attendance WHERE employee_id=%s", (id,))
    cursor.execute("DELETE FROM employees WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------- EDIT EMPLOYEE ----------------
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    if admin_required():
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        salary_raw = request.form.get('salary', '')
        check_in = request.form.get('check_in', '')
        check_out = request.form.get('check_out', '')

        if not name:
            conn.close()
            return "Error: Employee name cannot be empty", 400

        if not salary_raw.isdigit() or int(salary_raw) <= 0:
            conn.close()
            return "Error: Salary must be a positive number", 400

        if not check_in or not check_out:
            conn.close()
            return "Error: Check-in and check-out times are required", 400

        salary = int(salary_raw)

        cursor.execute("""
            UPDATE employees
            SET name=%s, salary=%s, check_in=%s, check_out=%s
            WHERE id=%s
        """, (name, salary, check_in, check_out, id))

        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    employee = cursor.fetchone()
    conn.close()

    return render_template('edit_employee.html', employee=employee)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)