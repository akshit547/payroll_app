from flask import Blueprint, render_template, session, redirect
from db import get_db_connection
from datetime import date

employee = Blueprint('employee', __name__)

@employee.route('/')
def home():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    role = session.get('role')
    user_id = session.get('user_id')

    # 🔥 ADMIN DASHBOARD
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

    # 🔥 EMPLOYEE DASHBOARD
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