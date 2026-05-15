# 💼 Payroll Management System

A full-stack web application for managing employee attendance, salary calculation, and payroll operations — built with Python, Flask, and PostgreSQL.

**Live Demo:** [payroll-app-9tb8.onrender.com](https://payroll-app-9tb8.onrender.com)
---

## Features

### Admin
- Secure login with role-based access control
- Add, edit, and delete employees
- Mark daily attendance with actual check-in and check-out times
- View per-employee attendance calendar
- Calculate net salary with per-minute penalty deduction
- Dashboard with real-time present/absent count

### Employee
- Personal dashboard with monthly attendance summary
- View calculated net salary with full breakdown
- Gross salary, earned salary, penalty deduction all shown transparently

---

## Salary Calculation Logic

```
Earned Salary   = (Gross Salary / 30) × Present Days
Penalty Minutes = Late Arrival + Early Exit (beyond 15-min grace period)
Penalty Amount  = (Per Day Salary / 480 minutes) × Penalty Minutes
Net Salary      = Earned Salary − Penalty Amount
```

A **15-minute grace period** is applied before any deduction is calculated — meaning employees are not penalised for being slightly late or leaving slightly early.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Database | PostgreSQL (production), psycopg2 |
| Connection Pooling | psycopg2 ThreadedConnectionPool |
| Auth | Werkzeug password hashing, Flask sessions |
| Frontend | HTML5, CSS3, Bootstrap 5, Vanilla JS |
| Icons | Bootstrap Icons |
| Calendar | FullCalendar.js |
| Fonts | Google Fonts (Inter + Poppins) |
| Hosting | Render |
| CI/CD | GitHub Actions |
| Server | Gunicorn (WSGI) |

---

## Project Structure

```
payroll_app/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── Procfile                # Gunicorn start command for Render
├── .gitignore
├── tests/
│   └── test_app.py         # Pytest test suite
├── .github/
│   └── workflows/
│       └── deploy.yml      # CI/CD pipeline
└── templates/
    ├── index.html           # Admin dashboard
    ├── employee_dashboard.html
    ├── employee_profile.html
    ├── attendance.html
    ├── calendar.html
    ├── add_employee.html
    ├── edit_employee.html
    ├── result.html
    ├── login.html
    └── signup.html
```

---

## Local Setup

**Prerequisites:** Python 3.11+, PostgreSQL

```bash
# 1. Clone the repository
git clone https://github.com/akshit547/payroll_app.git
cd payroll_app

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/payroll"
export SECRET_KEY="your_secret_key_here"

# 5. Run the app
python app.py
```

App runs at `http://localhost:10000`

**Default admin credentials:**
```
Username: admin
Password: admin123
```

---

## CI/CD Pipeline

Every push to `main` triggers the GitHub Actions pipeline:

```
Push to main
    → Spin up Ubuntu + PostgreSQL
    → Install dependencies
    → Run pytest test suite
    → If all tests pass → trigger Render deploy
    → If any test fails → deploy blocked
```

This ensures broken code never reaches production.

---

## Security

- Passwords hashed using **PBKDF2 + salt** via Werkzeug — never stored in plain text
- **Parameterized SQL queries** throughout — protected against SQL injection
- **Role-based access control** — admin and employee routes are separately guarded
- **Secret key** loaded from environment variable — never hardcoded
- **Session cookies** are signed with the secret key — tamper-proof
- Debug routes removed from production

---

## Database Design

```
users
├── id (PK)
├── username
├── password (hashed)
└── role (admin / employee)

employees
├── id (PK)
├── name
├── salary
├── user_id (FK → users)
├── check_in (expected time)
└── check_out (expected time)

attendance
├── id (PK)
├── employee_id (FK → employees, indexed)
├── user_id (FK → users)
├── date (indexed)
├── status (present / absent, indexed)
├── check_in_time (actual)
└── check_out_time (actual)
```

---

## Performance Optimisations

- **Connection Pooling** — `ThreadedConnectionPool` with min=1, max=10 connections. Eliminates the 200–800ms TCP handshake overhead on every request that comes with opening fresh connections
- **Database Indexes** — on `employee_id`, `date`, and `status` columns in the attendance table for fast query execution
- **UptimeRobot** — pings the app every 5 minutes to prevent Render free-tier cold starts

---

## Screenshots

> Admin Dashboard
> Salary Result

<img width="1355" height="687" alt="image" src="https://github.com/user-attachments/assets/12678f45-6b58-41c6-b455-4b8fe93ae71a" />
<img width="1355" height="687" alt="image" src="https://github.com/user-attachments/assets/afbc4500-c803-4bfb-b412-f653399c715a" />

---

## What I Learned

- Designing role-based authentication from scratch without any auth library
- Real-world database performance issues — identified cold connection overhead and fixed it with connection pooling
- Safe database migration patterns using `ALTER TABLE` with specific exception handling
- Setting up a proper CI/CD pipeline that blocks deploys on test failure
- The difference between earned salary vs gross salary in payroll logic

---

## Author

**Akshit** — Second year B.Tech IT, NIT Jalandhar

[![GitHub](https://img.shields.io/badge/GitHub-akshit547-black?style=flat-square&logo=github)](https://github.com/akshit547)

---

## License

This project is open source and available under the [MIT License](LICENSE).
