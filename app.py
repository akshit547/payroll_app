from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from datetime import date
import io
import os

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

# ---------------- DB ----------------
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        salary INTEGER,
        user_id INTEGER
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        user_id INTEGER,
        date TEXT,
        status TEXT
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# ---------------- ADMIN ----------------
def create_admin():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users VALUES (NULL, ?, ?, ?)",
            ("admin", "admin123", "admin")
        )
        conn.commit()

    conn.close()

create_admin()

# ---------------- AUTH ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users VALUES (NULL, ?, ?, ?)",
            (request.form['username'], request.form['password'], "employee")
        )

        conn.commit()
        conn.close()
        return redirect('/login')

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (request.form['username'], request.form['password'])
        )

        user = cursor.fetchone()
        conn.close()

        if user:
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

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    role = session['role']
    user_id = session['user_id']

    if role == "admin":
        cursor.execute("SELECT * FROM employees")
        employees = cursor.fetchall()

        today = date.today().isoformat()

        cursor.execute("SELECT COUNT(*) FROM attendance WHERE status='present' AND date=?", (today,))
        present_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM attendance WHERE status='absent' AND date=?", (today,))
        absent_today = cursor.fetchone()[0]

        conn.close()

        return render_template(
            'index.html',
            employees=employees,
            role=role,
            present_today=present_today,
            absent_today=absent_today
        )

    else:
        cursor.execute("SELECT * FROM employees WHERE user_id=?", (user_id,))
        emp = cursor.fetchone()

        if not emp:
            return "No data assigned"

        month = date.today().strftime("%Y-%m")

        cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id=? AND status='present' AND date LIKE ?", (emp[0], f"{month}%"))
        present = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id=? AND status='absent' AND date LIKE ?", (emp[0], f"{month}%"))
        absent = cursor.fetchone()[0]

        conn.close()

        return render_template("employee_dashboard.html", employee=emp, present=present, absent=absent)

# ---------------- ADD ----------------
@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if session['role'] != "admin":
        return "Access denied"

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute(
            "INSERT INTO employees VALUES (NULL, ?, ?, ?)",
            (request.form['name'], request.form['salary'], request.form['user_id'])
        )
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

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    today = date.today().isoformat()

    if request.method == 'POST':
        cursor.execute("DELETE FROM attendance WHERE employee_id=? AND date=?", (id, today))
        cursor.execute(
            "INSERT INTO attendance VALUES (NULL, ?, ?, ?, ?)",
            (id, session['user_id'], today, request.form['status'])
        )
        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    emp = cursor.fetchone()

    cursor.execute("SELECT date, status FROM attendance WHERE employee_id=? ORDER BY date DESC", (id,))
    records = cursor.fetchall()

    conn.close()

    return render_template("attendance.html", employee=emp, records=records,today=today)

# ---------------- PDF ----------------
@app.route('/payslip/<int:id>')
def payslip(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    emp = cursor.fetchone()

    month = date.today().strftime("%Y-%m")

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id=? AND status='present' AND date LIKE ?", (id, f"{month}%"))
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

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    emp = cursor.fetchone()

    month = date.today().strftime("%Y-%m")

    cursor.execute("""
    SELECT COUNT(*) FROM attendance
    WHERE employee_id=? AND status='present' AND date LIKE ?
    """, (id, f"{month}%"))

    present_days = cursor.fetchone()[0]

    conn.close()

    per_day = emp[2] / 30
    total = int(per_day * present_days)

    return render_template(
        'result.html',
        name=emp[1],
        total=total,
        days=present_days
    )

#calendar
@app.route('/calendar/<int:id>')
def calendar_view(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    employee = cursor.fetchone()

    cursor.execute(
        "SELECT date, status FROM attendance WHERE employee_id=?",
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

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Employee details
    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    emp = cursor.fetchone()

    # Monthly stats
    month = date.today().strftime("%Y-%m")

    cursor.execute("""
    SELECT COUNT(*) FROM attendance
    WHERE employee_id=? AND status='present' AND date LIKE ?
    """, (id, f"{month}%"))
    present = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*) FROM attendance
    WHERE employee_id=? AND status='absent' AND date LIKE ?
    """, (id, f"{month}%"))
    absent = cursor.fetchone()[0]

    # History
    cursor.execute("""
    SELECT date, status FROM attendance
    WHERE employee_id=? ORDER BY date DESC
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
# -------------------- EDIT --------------------

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') != "admin":
        return "Access denied"

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        salary = int(request.form['salary'])

        cursor.execute(
            "UPDATE employees SET name=?, salary=? WHERE id=?",
            (name, salary, id)
        )

        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    employee = cursor.fetchone()

    conn.close()
    return render_template('edit_employee.html', employee=employee)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000,debug=False)