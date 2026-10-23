import os
import re
import secrets
import sqlite3
from functools import wraps
from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from predictor import (predict_student, FEATURES, FEATURE_LABELS, LIMITS,
                       CATEGORY_LABELS)

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "students.db")
KEY_PATH = os.path.join(BASE, "secret.key")


def load_secret_key():
    """Use SECRET_KEY from the environment, else create and keep a random one."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    if not os.path.exists(KEY_PATH):
        with open(KEY_PATH, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(KEY_PATH) as fh:
        return fh.read().strip()


app = Flask(__name__)
app.secret_key = load_secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS students(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, roll_no TEXT NOT NULL, class_name TEXT NOT NULL,
  UNIQUE(user_id, roll_no));
CREATE TABLE IF NOT EXISTS records(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  term TEXT NOT NULL, attendance REAL, previous_marks REAL,
  assignment_score REAL, study_hours REAL, predicted REAL, category TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

LATEST_SQL = """
SELECT s.id, s.name, s.roll_no, s.class_name, r.term, r.attendance,
       r.previous_marks, r.assignment_score, r.study_hours, r.predicted, r.category
FROM students s JOIN records r
  ON r.id = (SELECT MAX(id) FROM records WHERE student_id = s.id)
"""

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    # An older single-teacher database has no user_id column: keep it as a backup.
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as db:
            cols = [r[1] for r in db.execute("PRAGMA table_info(students)")]
        if cols and "user_id" not in cols:
            os.replace(DB_PATH, os.path.join(BASE, "students_old_backup.db"))
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)


# ---------- security helpers ----------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Your session expired. Go back, reload the page and try again.")


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def my_student(db, sid):
    """Return the student only if it belongs to the logged-in user."""
    s = db.execute("SELECT * FROM students WHERE id = ? AND user_id = ?",
                   (sid, session["user_id"])).fetchone()
    if not s:
        abort(404)
    return s


@app.context_processor
def inject():
    return {"CATEGORY_LABELS": CATEGORY_LABELS, "FEATURES": FEATURES,
            "FEATURE_LABELS": FEATURE_LABELS, "LIMITS": LIMITS,
            "csrf_token": csrf_token}


# ---------- records ----------
def parse_record(form):
    vals, errs = {}, []
    for f in FEATURES:
        lo, hi = LIMITS[f]
        try:
            v = float(form.get(f, ""))
        except ValueError:
            errs.append(f"{FEATURE_LABELS[f]} must be a number.")
            continue
        if not lo <= v <= hi:
            errs.append(f"{FEATURE_LABELS[f]} must be between {lo} and {hi}.")
            continue
        vals[f] = v
    return vals, errs


def save_record(db, student_id, term, vals):
    res = predict_student(vals)
    db.execute(
        "INSERT INTO records(student_id, term, attendance, previous_marks,"
        " assignment_score, study_hours, predicted, category) VALUES(?,?,?,?,?,?,?,?)",
        (student_id, term, vals["attendance"], vals["previous_marks"],
         vals["assignment_score"], vals["study_hours"], res["score"], res["category"]))


# ---------- accounts ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        errs = []
        if not USERNAME_RE.match(username):
            errs.append("Username must be 3-30 characters: letters, numbers, _ or .")
        if len(pw) < 8:
            errs.append("Password must be at least 8 characters.")
        if pw != request.form.get("confirm", ""):
            errs.append("The two passwords do not match.")
        if not errs:
            db = get_db()
            try:
                cur = db.execute("INSERT INTO users(username, password_hash) VALUES(?,?)",
                                 (username, generate_password_hash(pw)))
                db.commit()
            except sqlite3.IntegrityError:
                errs.append("That username is taken. Try another one.")
            else:
                session.clear()
                session["user_id"], session["user"] = cur.lastrowid, username
                flash("Account created. Add your first student to get started.", "ok")
                return redirect(url_for("dashboard"))
        for e in errs:
            flash(e, "error")
    return render_template("register.html", username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (u,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"], session["user"] = user["id"], user["username"]
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("Login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    q = request.args.get("q", "").strip()
    cls = request.args.get("class", "")
    cat = request.args.get("category", "")
    where, params = ["s.user_id = ?"], [session["user_id"]]
    if q:
        where.append("(s.name LIKE ? OR s.roll_no LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if cls:
        where.append("s.class_name = ?")
        params.append(cls)
    if cat:
        where.append("r.category = ?")
        params.append(cat)
    sql = LATEST_SQL + " WHERE " + " AND ".join(where) + " ORDER BY r.predicted ASC"
    rows = db.execute(sql, params).fetchall()
    classes = [r[0] for r in db.execute(
        "SELECT DISTINCT class_name FROM students WHERE user_id = ? ORDER BY 1",
        (session["user_id"],))]

    n = len(rows)
    stats = {
        "count": n,
        "avg_pred": round(sum(r["predicted"] for r in rows) / n, 1) if n else 0,
        "avg_att": round(sum(r["attendance"] for r in rows) / n, 1) if n else 0,
        "support": sum(1 for r in rows if r["category"] == "support"),
    }
    cat_counts = [sum(1 for r in rows if r["category"] == k) for k in CATEGORY_LABELS]
    edges = [0, 40, 50, 60, 70, 80, 101]
    bin_labels = ["<40", "40-49", "50-59", "60-69", "70-79", "80+"]
    bins = [sum(1 for r in rows if edges[i] <= r["predicted"] < edges[i + 1])
            for i in range(len(bin_labels))]
    return render_template("dashboard.html", rows=rows, stats=stats, classes=classes,
                           q=q, cls=cls, cat=cat, cat_counts=cat_counts,
                           bin_labels=bin_labels, bins=bins)


@app.route("/students/new", methods=["GET", "POST"])
@login_required
def add_student():
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name = form.get("name", "").strip()
        roll = form.get("roll_no", "").strip()
        cls = form.get("class_name", "").strip()
        term = form.get("term", "").strip() or "Term 1"
        vals, errs = parse_record(form)
        if not (name and roll and cls):
            errs.insert(0, "Name, roll number and class are required.")
        if not errs:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO students(user_id, name, roll_no, class_name) VALUES(?,?,?,?)",
                    (session["user_id"], name, roll, cls))
            except sqlite3.IntegrityError:
                flash(f"Roll number {roll} already exists in your list.", "error")
                return render_template("add_student.html", form=form)
            save_record(db, cur.lastrowid, term, vals)
            db.commit()
            flash(f"Added {name}.", "ok")
            return redirect(url_for("student", sid=cur.lastrowid))
        for e in errs:
            flash(e, "error")
    return render_template("add_student.html", form=form)


@app.route("/students/<int:sid>")
@login_required
def student(sid):
    db = get_db()
    s = my_student(db, sid)
    records = db.execute("SELECT * FROM records WHERE student_id = ? ORDER BY id", (sid,)).fetchall()
    latest = records[-1]
    latest_vals = {f: latest[f] for f in FEATURES}
    result = predict_student(latest_vals)
    max_abs = max([abs(c["impact"]) for c in result["contributions"]] + [1])
    return render_template("student.html", s=s, records=records, latest=latest,
                           latest_vals=latest_vals, result=result, max_abs=max_abs,
                           trend_labels=[r["term"] for r in records],
                           trend_values=[r["predicted"] for r in records])


@app.route("/students/<int:sid>/record", methods=["POST"])
@login_required
def add_record(sid):
    db = get_db()
    my_student(db, sid)
    vals, errs = parse_record(request.form)
    if errs:
        for e in errs:
            flash(e, "error")
    else:
        count = db.execute("SELECT COUNT(*) FROM records WHERE student_id = ?", (sid,)).fetchone()[0]
        term = request.form.get("term", "").strip() or f"Term {count + 1}"
        save_record(db, sid, term, vals)
        db.commit()
        flash("New record saved.", "ok")
    return redirect(url_for("student", sid=sid))


@app.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def delete_student(sid):
    db = get_db()
    my_student(db, sid)
    db.execute("DELETE FROM students WHERE id = ?", (sid,))
    db.commit()
    flash("Student deleted.", "ok")
    return redirect(url_for("dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
