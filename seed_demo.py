"""Adds demo students so the dashboard is not empty:  python seed_demo.py"""
import random
from werkzeug.security import generate_password_hash
from app import app, get_db, save_record, init_db

random.seed(7)
NAMES = ["Aarav Sharma", "Diya Patel", "Rohan Mehta", "Ananya Iyer", "Kabir Singh",
         "Meera Nair", "Arjun Reddy", "Ishita Das", "Vivaan Gupta", "Saanvi Rao",
         "Aditya Joshi", "Navya Menon", "Rahul Verma", "Priya Kulkarni", "Karan Malhotra"]

init_db()
with app.app_context():
    db = get_db()
    u = db.execute("SELECT id FROM users WHERE username = 'demo'").fetchone()
    if u:
        uid = u["id"]
    else:
        uid = db.execute("INSERT INTO users(username, password_hash) VALUES(?,?)",
                         ("demo", generate_password_hash("demo12345"))).lastrowid
    for i, name in enumerate(NAMES, 1):
        roll = f"CS{i:03d}"
        if db.execute("SELECT 1 FROM students WHERE user_id = ? AND roll_no = ?", (uid, roll)).fetchone():
            continue
        cur = db.execute("INSERT INTO students(user_id, name, roll_no, class_name) VALUES(?,?,?,?)",
                         (uid, name, roll, "CSBT-2A"))
        base = random.uniform(40, 90)
        for t in range(1, 4):
            drift = random.uniform(-6, 9) * (t - 1)
            prev = min(100, max(15, base + drift))
            save_record(db, cur.lastrowid, f"Term {t}", {
                "attendance": round(min(100, max(40, prev + random.uniform(-15, 15))), 1),
                "previous_marks": round(prev, 1),
                "assignment_score": round(min(100, max(20, prev + random.uniform(-12, 12))), 1),
                "study_hours": round(min(8, max(0.5, prev / 30 + random.uniform(-1, 1))), 1),
            })
    db.commit()
print("Demo students added. Log in with demo / demo12345")
