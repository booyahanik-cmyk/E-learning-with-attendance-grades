"""E-Learning Course Management System - Flask + SQLite backend."""
import sqlite3, random, string
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, g, abort)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = "elearning.db"

# Demo reward partners (sample vouchers, not real coupons)
PARTNERS = [("Flipkart", "10% OFF"), ("Amazon", "5% OFF"),
            ("Swiggy", "15% OFF"), ("Myntra", "10% OFF"), ("Zomato", "20% OFF")]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE,
  password TEXT, role TEXT DEFAULT 'student');
CREATE TABLE IF NOT EXISTS courses(
  id INTEGER PRIMARY KEY, title TEXT, category TEXT, icon TEXT,
  description TEXT, instructor_id INTEGER);
CREATE TABLE IF NOT EXISTS lessons(
  id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT,
  content TEXT, position INTEGER);
CREATE TABLE IF NOT EXISTS enrollments(
  user_id INTEGER, course_id INTEGER, UNIQUE(user_id, course_id));
CREATE TABLE IF NOT EXISTS progress(
  user_id INTEGER, lesson_id INTEGER, UNIQUE(user_id, lesson_id));
CREATE TABLE IF NOT EXISTS vouchers(
  id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER,
  brand TEXT, discount TEXT, code TEXT, UNIQUE(user_id, course_id));
"""

# ---------- database helpers ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM users").fetchone():
        conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                     ("Admin Teacher", "teacher@demo.com",
                      generate_password_hash("teacher123"), "instructor"))
        seed = [
            ("Python for Beginners", "Programming", "🐍",
             "Learn Python from scratch: variables, loops, functions and more.",
             ["Introduction to Python", "Variables and Data Types",
              "Loops and Conditions", "Functions"]),
            ("Web Development Basics", "Web", "🌐",
             "Build your first website with HTML, CSS and JavaScript.",
             ["HTML Structure", "Styling with CSS", "JavaScript Basics"]),
            ("Data Science Starter", "Data", "📊",
             "Explore data with NumPy, Pandas and simple charts.",
             ["What is Data Science?", "NumPy Arrays", "Pandas DataFrames"]),
        ]
        for title, cat, icon, desc, lessons in seed:
            cur = conn.execute("INSERT INTO courses(title,category,icon,description,instructor_id)"
                               " VALUES(?,?,?,?,1)", (title, cat, icon, desc))
            for i, l in enumerate(lessons, 1):
                conn.execute("INSERT INTO lessons(course_id,title,content,position) VALUES(?,?,?,?)",
                             (cur.lastrowid, l, f"Lesson notes for: {l}. Read carefully, "
                              "practise the examples, then mark the lesson complete.", i))
    conn.commit()
    conn.close()

# ---------- auth helpers ----------
def current_user():
    uid = session.get("uid")
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None

@app.context_processor
def inject_user():
    return {"user": current_user()}

def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("uid"):
            flash("Please log in first.", "warn")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper

def course_progress(uid, cid):
    total = db().execute("SELECT COUNT(*) FROM lessons WHERE course_id=?", (cid,)).fetchone()[0]
    done = db().execute("""SELECT COUNT(*) FROM progress p JOIN lessons l ON l.id=p.lesson_id
                           WHERE p.user_id=? AND l.course_id=?""", (uid, cid)).fetchone()[0]
    pct = int(done * 100 / total) if total else 0
    return total, done, pct

# ---------- routes ----------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", "")
    sql = """SELECT c.*, u.name AS teacher,
             (SELECT COUNT(*) FROM lessons WHERE course_id=c.id) AS n_lessons,
             (SELECT COUNT(*) FROM enrollments WHERE course_id=c.id) AS n_students
             FROM courses c JOIN users u ON u.id=c.instructor_id
             WHERE (c.title LIKE ? OR c.description LIKE ?)"""
    args = [f"%{q}%", f"%{q}%"]
    if cat:
        sql += " AND c.category=?"
        args.append(cat)
    courses = db().execute(sql + " ORDER BY c.id DESC", args).fetchall()
    cats = [r[0] for r in db().execute("SELECT DISTINCT category FROM courses")]
    return render_template("index.html", courses=courses, cats=cats, q=q, cat=cat)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        try:
            db().execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                         (f["name"], f["email"].lower(),
                          generate_password_hash(f["password"]), f["role"]))
            db().commit()
            flash("Account created! Please log in.", "ok")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "warn")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?",
                         (request.form["email"].lower(),)).fetchone()
        if u and check_password_hash(u["password"], request.form["password"]):
            session["uid"] = u["id"]
            return redirect(url_for("index"))
        flash("Wrong email or password.", "warn")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/course/<int:cid>")
def course(cid):
    c = db().execute("""SELECT c.*, u.name AS teacher FROM courses c
                        JOIN users u ON u.id=c.instructor_id WHERE c.id=?""", (cid,)).fetchone()
    if not c:
        abort(404)
    lessons = db().execute("SELECT * FROM lessons WHERE course_id=? ORDER BY position", (cid,)).fetchall()
    uid = session.get("uid")
    enrolled, done_ids, voucher, stats = False, set(), None, (len(lessons), 0, 0)
    if uid:
        enrolled = bool(db().execute("SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?",
                                     (uid, cid)).fetchone())
        done_ids = {r[0] for r in db().execute("SELECT lesson_id FROM progress WHERE user_id=?", (uid,))}
        voucher = db().execute("SELECT * FROM vouchers WHERE user_id=? AND course_id=?",
                               (uid, cid)).fetchone()
        stats = course_progress(uid, cid)
    return render_template("course.html", c=c, lessons=lessons, enrolled=enrolled,
                           done_ids=done_ids, voucher=voucher, stats=stats)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_course():
    if current_user()["role"] != "instructor":
        flash("Only instructors can create courses.", "warn")
        return redirect(url_for("index"))
    if request.method == "POST":
        f = request.form
        cur = db().execute("INSERT INTO courses(title,category,icon,description,instructor_id)"
                           " VALUES(?,?,?,?,?)",
                           (f["title"], f["category"], f["icon"] or "📘",
                            f["description"], session["uid"]))
        lines = [l.strip() for l in f["lessons"].splitlines() if l.strip()]
        for i, line in enumerate(lines, 1):
            title, _, body = line.partition("|")
            db().execute("INSERT INTO lessons(course_id,title,content,position) VALUES(?,?,?,?)",
                         (cur.lastrowid, title.strip(), body.strip() or "Lesson content coming soon.", i))
        db().commit()
        flash("Course created successfully!", "ok")
        return redirect(url_for("course", cid=cur.lastrowid))
    return render_template("add_course.html")

@app.route("/delete/<int:cid>", methods=["POST"])
@login_required
def delete_course(cid):
    c = db().execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
    if c and c["instructor_id"] == session["uid"]:
        for t in ("lessons", "enrollments", "vouchers"):
            db().execute(f"DELETE FROM {t} WHERE course_id=?", (cid,))
        db().execute("DELETE FROM courses WHERE id=?", (cid,))
        db().commit()
        flash("Course deleted.", "ok")
    return redirect(url_for("index"))

@app.route("/enroll/<int:cid>", methods=["POST"])
@login_required
def enroll(cid):
    db().execute("INSERT OR IGNORE INTO enrollments VALUES(?,?)", (session["uid"], cid))
    db().commit()
    flash("You are enrolled. Happy learning!", "ok")
    return redirect(url_for("course", cid=cid))

@app.route("/complete/<int:lid>", methods=["POST"])
@login_required
def complete_lesson(lid):
    lesson = db().execute("SELECT * FROM lessons WHERE id=?", (lid,)).fetchone()
    if not lesson:
        abort(404)
    uid, cid = session["uid"], lesson["course_id"]
    db().execute("INSERT OR IGNORE INTO progress VALUES(?,?)", (uid, lid))
    total, done, _ = course_progress(uid, cid)
    if total and done == total:  # course finished -> reward voucher
        brand, disc = random.choice(PARTNERS)
        code = brand[:3].upper() + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        db().execute("INSERT OR IGNORE INTO vouchers(user_id,course_id,brand,discount,code)"
                     " VALUES(?,?,?,?,?)", (uid, cid, brand, disc, code))
        flash("🎉 Course completed! You earned a voucher.", "ok")
    db().commit()
    return redirect(url_for("course", cid=cid))

@app.route("/my-learning")
@login_required
def my_learning():
    uid = session["uid"]
    rows = db().execute("""SELECT c.* FROM courses c JOIN enrollments e
                           ON e.course_id=c.id WHERE e.user_id=?""", (uid,)).fetchall()
    items = [(r, course_progress(uid, r["id"])) for r in rows]
    vouchers = db().execute("""SELECT v.*, c.title FROM vouchers v JOIN courses c
                               ON c.id=v.course_id WHERE v.user_id=?""", (uid,)).fetchall()
    return render_template("my_learning.html", items=items, vouchers=vouchers)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
