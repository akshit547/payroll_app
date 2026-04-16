from flask import Flask, render_template, request, redirect
from datetime import date
import sqlite3

app = Flask(__name__)

# 🧱 Initialize Database
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            salary INTEGER
        )
    ''')
    cursor.execute('''
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,
    date TEXT,
    status TEXT
)
''')

    conn.commit()
    conn.close()

init_db()

# 🏠 Home Route
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    conn.close()

    return render_template('index.html', employees=employees)

# ➕ Add Employee
@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        name = request.form['name']
        salary = int(request.form['salary'])

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO employees (name, salary) VALUES (?, ?)",
            (name, salary)
        )

        conn.commit()
        conn.close()

        return redirect('/')

    return render_template('add_employee.html')

# 🧮 Calculate Salary
@app.route('/calculate/<int:id>')
def calculate(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    employee = cursor.fetchone()

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE employee_id=? AND status='present'",
        (id,)
    )
    present_days = cursor.fetchone()[0]

    conn.close()

    per_day = employee[2] / 30
    total = per_day * present_days

    return render_template(
        'result.html',
        name=employee[1],
        total=int(total),
        days=present_days,
        overtime=0,
        bonus=0
    )

#delete employee
@app.route('/delete/<int:id>')
def delete_employee(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("DELETE FROM employees WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/')

#edit employee
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
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
@app.route('/attendance/<int:id>', methods=['GET', 'POST'])
def mark_attendance(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    from datetime import date
    today = date.today().isoformat()

    if request.method == 'POST':
        status = request.form['status']

        # Prevent duplicate entry for same day
        cursor.execute(
            "DELETE FROM attendance WHERE employee_id=? AND date=?",
            (id, today)
        )

        cursor.execute(
            "INSERT INTO attendance (employee_id, date, status) VALUES (?, ?, ?)",
            (id, today, status)
        )

        conn.commit()
        conn.close()

        return redirect('/')  

    # Fetch employee
    cursor.execute("SELECT * FROM employees WHERE id=?", (id,))
    employee = cursor.fetchone()

    # Fetch attendance history
    cursor.execute(
        "SELECT date, status FROM attendance WHERE employee_id=? ORDER BY date DESC",
        (id,)
    )
    records = cursor.fetchall()

    conn.close()

    return render_template(
        'attendance.html',
        employee=employee,
        records=records,
        today=today
    )

# ▶️ Run App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)