from flask import Flask, render_template, request, redirect, session, send_file,jsonify
from datetime import date,datetime
import io
import os,psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__) 
app.secret_key = os.environ.get("SECRET_KEY", "fallback_only_for_local_dev")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True

# ---------------- DB ----------------
def get_db_connection():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"),sslmode='require')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY ,
        username TEXT,
        password TEXT,
        role TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id SERIAL PRIMARY KEY ,
        name TEXT,
        salary INTEGER,
        user_id INTEGER
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY ,
        employee_id INTEGER,
        user_id INTEGER,
        date TEXT,
        status TEXT
    )
    ''')
        # Add columns if they don't exist (safe migration)
    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN check_in TIME")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE employees ADD COLUMN check_out TIME")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN check_in_time TIME")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN check_out_time TIME")
    except:
        pass

    conn.commit()
    conn.close()

init_db()


# ---------------- ADMIN ----------------
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

# ---------------- AUTH ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        hashed_password = generate_password_hash(request.form['password'])

        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) RETURNING id",
            (request.form['username'], hashed_password, "employee")
        )
        user_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO employees (user_id, name, salary) VALUES (%s, %s, %s)",
            (user_id, request.form['username'], 0)
        )
        conn.commit()
        conn.close()
        return redirect('/login')

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
             "SELECT * FROM users WHERE username=%s",
             (request.form['username'],)
        )

        user = cursor.fetchone()
        conn.close() 

        if user and check_password_hash(user[2], request.form['password']):
            session['user_id'] = user[0]
            session['role'] = user[3]
            return redirect('/')
        else:
            return "Invalid credentials"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- HOME ----------------
@app.route('/')
def home():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    role = session.get('role')
    user_id = session.get('user_id')

    if role == "admin":
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
            role=role,
            present_today=present_today,
            absent_today=absent_today
        )

    # EMPLOYEE DASHBOARD
    else:
        cursor.execute(
            "SELECT * FROM employees WHERE user_id=%s",
            (user_id,)
        )
        emp = cursor.fetchone()


        if not emp:
            conn.close()
            return "⚠️ No employee profile found. Contact admin."

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
    
# ---------------- ADD ----------------
@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if session['role'] != "admin":
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
INSERT INTO employees (name, salary, user_id, check_in, check_out)
VALUES (%s, %s, %s, %s, %s)
""", (
    request.form['name'],
    request.form['salary'],
    request.form['user_id'],
    request.form['check_in'],
    request.form['check_out']
))
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
    if session['role'] != "admin":
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    if request.method == 'POST':
        cursor.execute("DELETE FROM attendance WHERE employee_id=%s AND date=%s", (id, today))
        cursor.execute("""
INSERT INTO attendance 
(employee_id, user_id, date, status, check_in_time, check_out_time)
VALUES (%s, %s, %s, %s, %s, %s)
""", (
    id,
    session['user_id'],
    today,
    request.form['status'],
    request.form['check_in_time'],
    request.form['check_out_time']
))
        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    cursor.execute("SELECT date, status FROM attendance WHERE employee_id=%s ORDER BY date DESC", (id,))
    records = cursor.fetchall()

    conn.close()

    return render_template("attendance.html", employee=emp, records=records,today=today)

# ---------------- PDF ----------------
@app.route('/payslip/<int:id>')
def payslip(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    month = date.today().strftime("%Y-%m")

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id=%s AND status='present' AND date LIKE %s", (id, f"{month}%"))
    days = cursor.fetchone()[0]

    conn.close()

    total = int((emp[2]/30) * days)

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

# ---------------- CALCULATE ----------------
@app.route('/calculate/<int:id>')
def calculate(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔥 Get employee
    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    if not emp:
        conn.close()
        return "Employee not found"

    expected_in = emp[4]
    expected_out = emp[5]

    # ❗ Check if working hours set
    if not expected_in or not expected_out:
        conn.close()
        return "⚠️ Working hours not set for this employee"

    # 🔥 Get current month records
    month = date.today().strftime("%Y-%m")

    cursor.execute("""
    SELECT check_in_time, check_out_time, date 
    FROM attendance 
    WHERE employee_id=%s AND date LIKE %s
    """, (id, f"{month}%"))

    records = cursor.fetchall()

    if not records:
        conn.close()
        return "No attendance data for this month"

    fmt = "%H:%M:%S"

    expected_in = datetime.strptime(str(expected_in), fmt)
    expected_out = datetime.strptime(str(expected_out), fmt)

    total_penalty_minutes = 0

    # 🔥 Loop through all days
    for r in records:
        actual_in = r[0]
        actual_out = r[1]

        # skip incomplete records
        if not actual_in or not actual_out:
            continue

        actual_in = datetime.strptime(str(actual_in), fmt)
        actual_out = datetime.strptime(str(actual_out), fmt)

        late = max(0, (actual_in - expected_in).total_seconds() / 60)
        early = max(0, (expected_out - actual_out).total_seconds() / 60)

        total_penalty_minutes += (late + early)

    # 🔥 Salary calculation
    salary = emp[2]

    working_minutes_per_day = 8 * 60
    per_day_salary = salary / 30
    per_minute_salary = per_day_salary / working_minutes_per_day

    total_deduction = per_minute_salary * total_penalty_minutes
    final_salary = int(salary - total_deduction)

    conn.close()

    return render_template(
        'result.html',
        name=emp[1],
        total=final_salary,
        penalty=int(total_deduction),
        minutes=int(total_penalty_minutes)
    )
#------------- CALENDAR ----------------
@app.route('/calendar/<int:id>')
def calendar_view(id):
    if 'user_id' not in session:
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

    return render_template(
        'calendar.html',
        employee=employee,
        records=records
    )
# ---------------- Employee profile----------------
@app.route('/employee/<int:id>')
def employee_profile(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Employee details
    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    # Monthly stats
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

    # History
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

# ---------------- DELETE ----------------
@app.route('/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    # 🔐 Only logged-in admin allowed
    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') != "admin":
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔥 Optional: delete related attendance first (important)
    cursor.execute("DELETE FROM attendance WHERE employee_id=%s", (id,))

    # 🔥 Delete employee
    cursor.execute("DELETE FROM employees WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect('/')
# -------------------- EDIT --------------------

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') != "admin":
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        salary = int(request.form['salary'])

        cursor.execute("""
UPDATE employees 
SET name=%s, salary=%s, check_in=%s, check_out=%s 
WHERE id=%s
""", (name, salary, request.form['check_in'], request.form['check_out'], id))

        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    employee = cursor.fetchone()

    conn.close()
    return render_template('edit_employee.html', employee=employee)



# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000,debug=True)