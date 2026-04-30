from flask import Blueprint, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection

auth = Blueprint('auth', __name__)

@auth.route('/signup', methods=['GET', 'POST'])
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


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username=%s", (request.form['username'],))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], request.form['password']):
            session['user_id'] = user[0]
            session['role'] = user[3]
            return redirect('/')
        return "Invalid credentials"

    return render_template('login.html')


@auth.route('/logout')
def logout():
    session.clear()
    return redirect('/login')