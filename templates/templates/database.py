import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


def _database_path(app=None):
    active_app = app or current_app
    return Path(active_app.root_path) / "pianova.db"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(_database_path())
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def init_db(app):
    db = sqlite3.connect(_database_path(app))
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


def fetch_user_by_username(username):
    return get_db().execute(
        "SELECT id, username, password, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()


def create_user(username, password_hash, role='user'):
    db = get_db()
    db.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    db.commit()


def reset_password(username, new_password_hash):
    db = get_db()
    db.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (new_password_hash, username),
    )
    db.commit()


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


def get_all_accounts():
    return get_db().execute(
        "SELECT id, username, password, role FROM users ORDER BY id DESC"
    ).fetchall()


def get_user_metrics(user_id, current_level):
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
        'current_level': current_level,
    }


if __name__ == "__main__":
    print("Run the Flask app to initialize the database.")