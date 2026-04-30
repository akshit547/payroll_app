from flask import Flask, render_template, request, redirect, session, send_file
from datetime import date
import io
import os,psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from routes.auth import auth
from routes.employee import employee
from routes.admin import admin

app = Flask(__name__) 
app.secret_key = "super_secret_key_123"
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True


# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(employee)
app.register_blueprint(admin)

# ---------------- ADD ----------------
@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if session['role'] != "admin":
        return "Access denied"

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute( "INSERT INTO employees (name, salary, user_id) VALUES (%s, %s, %s)", (request.form['name'], request.form['salary'], request.form['user_id']) )
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
        cursor.execute( "INSERT INTO attendance (employee_id, user_id, date, status) VALUES (%s, %s, %s, %s)", (id, session['user_id'], today, request.form['status']) )
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

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    emp = cursor.fetchone()

    month = date.today().strftime("%Y-%m")

    cursor.execute("""
    SELECT COUNT(*) FROM attendance
    WHERE employee_id=%s AND status='present' AND date LIKE %s
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

        cursor.execute(
            "UPDATE employees SET name=%s, salary=%s WHERE id=%s",
            (name, salary, id)
        )

        conn.commit()
        conn.close()
        return redirect('/')

    cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
    employee = cursor.fetchone()

    conn.close()
    return render_template('edit_employee.html', employee=employee)



# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000,debug=False)