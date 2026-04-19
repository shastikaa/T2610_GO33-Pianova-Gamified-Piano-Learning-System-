import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder='static')
app.secret_key = "secret123"

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "pianova.db"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE_PATH)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_name TEXT NOT NULL,
            description TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_id INTEGER,
            task_name TEXT,
            correct_answer TEXT,
            FOREIGN KEY (level_id) REFERENCES levels(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            score INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            level_id INTEGER,
            status TEXT,
            UNIQUE(user_id, level_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (level_id) REFERENCES levels(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            completion_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    seed_user(cursor, 'admin', 'admin123', 'admin')
    seed_user(cursor, 'student', '1234', 'user')

    levels = [
        (1, 'Level 1', 'Basic Notes'),
        (2, 'Level 2', 'Simple Melody'),
        (3, 'Level 3', 'Intermediate'),
        (4, 'Level 4', 'Final Challenge'),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO levels (id, level_name, description) VALUES (?, ?, ?)",
        levels,
    )

    db.commit()
    db.close()


def seed_user(cursor, username, password, role):
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role),
        )


def verify_password(stored_password, provided_password):
    if stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:'):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password


def fetch_user_by_username(username):
    return get_db().execute(
        "SELECT id, username, password, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)

    return wrapped_view


def role_required(expected_role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if session.get('role') != expected_role:
                flash('You do not have access to that page.', 'error')
                return redirect(url_for('home'))
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def save_progress(user_id, level_id, status):
    db = get_db()
    db.execute(
        """
        INSERT INTO progress (user_id, level_id, status)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, level_id) DO UPDATE SET status = excluded.status
        """,
        (user_id, level_id, status),
    )
    db.commit()


def add_score(user_id, game_type, score):
    db = get_db()
    db.execute(
        "INSERT INTO scores (user_id, game_type, score) VALUES (?, ?, ?)",
        (user_id, game_type, score),
    )
    db.commit()


def get_admin_metrics():
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
    total_admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    total_scores = db.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    completed_lessons = db.execute(
        "SELECT COUNT(*) FROM progress WHERE status = 'completed'"
    ).fetchone()[0]
    recent_users = db.execute(
        "SELECT username, role FROM users ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return {
        'total_users': total_users,
        'total_admins': total_admins,
        'total_scores': total_scores,
        'completed_lessons': completed_lessons,
        'recent_users': recent_users,
    }


def get_user_metrics(user_id):
    db = get_db()
    score_total = db.execute(
        "SELECT COALESCE(SUM(score), 0) FROM scores WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    completed = db.execute(
        "SELECT COUNT(*) FROM progress WHERE user_id = ? AND status = 'completed'",
        (user_id,),
    ).fetchone()[0]
    return {
        'score_total': score_total,
        'completed_lessons': completed,
        'current_level': session.get('level', 1),
    }


@app.route('/')
def home():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    if session.get('role') == 'user':
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = fetch_user_by_username(username)
        if user is None or not verify_password(user['password'], password):
            flash('Invalid username or password.', 'error')
            return render_template('login_new.html')

        session.clear()
        session['user_id'] = user['id']
        session['user'] = user['username']
        session['role'] = user['role']
        session['level'] = 1

        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))

    return render_template('login_new.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        if fetch_user_by_username(username) is not None:
            flash('That username is already taken.', 'error')
            return render_template('register.html')

        db = get_db()
        db.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), 'user'),
        )
        db.commit()

        flash('Account created. You can log in now.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    return render_template(
        'user_dashboard.html',
        username=session['user'],
        metrics=get_user_metrics(session['user_id']),
    )


@app.route('/admin-dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    return render_template(
        'admin_dashboard_new.html',
        username=session['user'],
        metrics=get_admin_metrics(),
    )


@app.route('/lessons')
@login_required
@role_required('user')
def lessons():
    session['level'] = max(session.get('level', 1), 1)
    return render_template('templates/index.html', level=session['level'])


@app.route('/game', methods=['GET', 'POST'])
@login_required
@role_required('user')
def game():
    message = ''

    if request.method == 'POST':
        answer = request.form.get('note')

        if answer == 'C':
            message = 'Correct! Level 2 unlocked.'
            session['level'] = max(session.get('level', 1), 2)
            save_progress(session['user_id'], 1, 'completed')
            add_score(session['user_id'], 'note-match', 10)
        else:
            message = 'Wrong answer. Try again.'

    return render_template('game.html', message=message)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


init_db()


if __name__ == '__main__':
    app.run(debug=True)
