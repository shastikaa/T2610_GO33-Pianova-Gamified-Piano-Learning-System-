import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


PROGRESS_STATUSES = ('not_started', 'in_progress', 'completed')


def _database_path(app=None):
    active_app = app or current_app
    return Path(active_app.root_path) / "pianova.db"


def _apply_pragmas(db):
    db.execute("PRAGMA foreign_keys = ON")


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(_database_path())
        g.db.row_factory = sqlite3.Row
        _apply_pragmas(g.db)
    return g.db


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def _table_columns(cursor, table_name):
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(cursor, table_name, column_name, definition):
    existing = _table_columns(cursor, table_name)
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _create_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_name TEXT NOT NULL,
            description TEXT,
            level_order INTEGER NOT NULL DEFAULT 1,
            is_locked INTEGER NOT NULL DEFAULT 0,
            unlock_score INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            correct_answer TEXT,
            task_type TEXT NOT NULL DEFAULT 'practice',
            max_score INTEGER NOT NULL DEFAULT 100,
            passing_score INTEGER NOT NULL DEFAULT 60,
            display_order INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (level_id) REFERENCES levels(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_type TEXT NOT NULL,
            score INTEGER NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level_id INTEGER,
            task_id INTEGER,
            quiz_name TEXT,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL DEFAULT 0,
            correct_answers INTEGER NOT NULL DEFAULT 0,
            attempt_no INTEGER NOT NULL DEFAULT 1,
            passed INTEGER NOT NULL DEFAULT 0,
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (level_id) REFERENCES levels(id) ON DELETE SET NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'completed')),
            progress_percent INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, level_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (level_id) REFERENCES levels(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_task_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'completed')),
            attempts INTEGER NOT NULL DEFAULT 0,
            best_score INTEGER NOT NULL DEFAULT 0,
            last_score INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            completed_at TEXT,
            UNIQUE(user_id, task_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_level_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'completed')),
            completed_tasks INTEGER NOT NULL DEFAULT 0,
            total_tasks INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0,
            best_score INTEGER NOT NULL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            last_activity_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, level_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (level_id) REFERENCES levels(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level_id INTEGER,
            cert_ref_id TEXT UNIQUE,
            certificate_no TEXT UNIQUE,
            title TEXT NOT NULL DEFAULT 'Pianova Completion Certificate',
            issued_for TEXT,
            score_snapshot INTEGER,
            completion_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (level_id) REFERENCES levels(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS practice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_type TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def _ensure_backward_compatibility_columns(cursor):
    # Older DB files may have created minimal versions of these tables.
    _add_column_if_missing(cursor, 'users', 'is_active', 'INTEGER NOT NULL DEFAULT 1')
    _add_column_if_missing(cursor, 'users', 'created_at', 'TEXT')
    _add_column_if_missing(cursor, 'users', 'updated_at', 'TEXT')

    _add_column_if_missing(cursor, 'levels', 'level_order', 'INTEGER NOT NULL DEFAULT 1')
    _add_column_if_missing(cursor, 'levels', 'is_locked', 'INTEGER NOT NULL DEFAULT 0')
    _add_column_if_missing(cursor, 'levels', 'unlock_score', 'INTEGER NOT NULL DEFAULT 0')
    _add_column_if_missing(cursor, 'levels', 'created_at', 'TEXT')
    _add_column_if_missing(cursor, 'levels', 'updated_at', 'TEXT')

    _add_column_if_missing(cursor, 'tasks', 'task_type', "TEXT NOT NULL DEFAULT 'practice'")
    _add_column_if_missing(cursor, 'tasks', 'max_score', 'INTEGER NOT NULL DEFAULT 100')
    _add_column_if_missing(cursor, 'tasks', 'passing_score', 'INTEGER NOT NULL DEFAULT 60')
    _add_column_if_missing(cursor, 'tasks', 'display_order', 'INTEGER NOT NULL DEFAULT 1')
    _add_column_if_missing(cursor, 'tasks', 'created_at', 'TEXT')
    _add_column_if_missing(cursor, 'tasks', 'updated_at', 'TEXT')

    _add_column_if_missing(cursor, 'scores', 'recorded_at', 'TEXT')

    _add_column_if_missing(cursor, 'progress', 'progress_percent', 'INTEGER NOT NULL DEFAULT 0')
    _add_column_if_missing(cursor, 'progress', 'started_at', 'TEXT')
    _add_column_if_missing(cursor, 'progress', 'completed_at', 'TEXT')
    _add_column_if_missing(cursor, 'progress', 'updated_at', 'TEXT')

    _add_column_if_missing(cursor, 'certificates', 'level_id', 'INTEGER')
    _add_column_if_missing(cursor, 'certificates', 'cert_ref_id', 'TEXT')
    _add_column_if_missing(cursor, 'certificates', 'certificate_no', 'TEXT')
    _add_column_if_missing(cursor, 'certificates', 'title', "TEXT NOT NULL DEFAULT 'Pianova Completion Certificate'")
    _add_column_if_missing(cursor, 'certificates', 'issued_for', 'TEXT')
    _add_column_if_missing(cursor, 'certificates', 'score_snapshot', 'INTEGER')
    _add_column_if_missing(cursor, 'certificates', 'created_at', 'TEXT')


def _backfill_timestamp_columns(cursor):
    cursor.execute("UPDATE users SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE users SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE levels SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE levels SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE tasks SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE tasks SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE scores SET recorded_at = COALESCE(recorded_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE progress SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")
    cursor.execute("UPDATE certificates SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")


def _backfill_certificate_reference_ids(cursor):
    rows = cursor.execute(
        """
        SELECT id
        FROM certificates
        WHERE cert_ref_id IS NULL OR TRIM(cert_ref_id) = ''
        ORDER BY id ASC
        """
    ).fetchall()

    for row in rows:
        cert_ref_id = f"CERT-{int(row[0]):06d}"
        cursor.execute(
            "UPDATE certificates SET cert_ref_id = ? WHERE id = ?",
            (cert_ref_id, row[0]),
        )


def _create_indexes(cursor):
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_level ON tasks(level_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_user ON scores(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_game_type ON scores(game_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_recorded_at ON scores(recorded_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_scores_user ON quiz_scores(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_scores_level ON quiz_scores(level_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_user ON progress(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_level ON progress(level_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_status ON progress(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_task_progress_user ON user_task_progress(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_task_progress_task ON user_task_progress(task_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_level_progress_user ON user_level_progress(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_level_progress_level ON user_level_progress(level_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_certificates_user ON certificates(user_id)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_certificates_ref_id_unique ON certificates(cert_ref_id) WHERE cert_ref_id IS NOT NULL")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_certificates_certificate_no_unique ON certificates(certificate_no) WHERE certificate_no IS NOT NULL")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_sessions_user ON practice_sessions(user_id)")


def _create_user_lookup_views(cursor):
    cursor.execute("DROP VIEW IF EXISTS scores_with_usernames")
    cursor.execute(
        """
        CREATE VIEW scores_with_usernames AS
        SELECT
            s.id,
            s.user_id,
            u.username,
            s.game_type,
            s.score,
            s.recorded_at
        FROM scores s
        JOIN users u ON u.id = s.user_id
        """
    )

    cursor.execute("DROP VIEW IF EXISTS quiz_scores_with_usernames")
    cursor.execute(
        """
        CREATE VIEW quiz_scores_with_usernames AS
        SELECT
            qs.id,
            qs.user_id,
            u.username,
            qs.level_id,
            COALESCE(l.level_name, 'N/A') AS level_name,
            qs.task_id,
            COALESCE(t.task_name, 'N/A') AS task_name,
            qs.quiz_name,
            qs.score,
            qs.total_questions,
            qs.correct_answers,
            qs.attempt_no,
            qs.passed,
            qs.submitted_at
        FROM quiz_scores qs
        JOIN users u ON u.id = qs.user_id
        LEFT JOIN levels l ON l.id = qs.level_id
        LEFT JOIN tasks t ON t.id = qs.task_id
        """
    )

    cursor.execute("DROP VIEW IF EXISTS progress_with_usernames")
    cursor.execute(
        """
        CREATE VIEW progress_with_usernames AS
        SELECT
            p.id,
            p.user_id,
            u.username,
            p.level_id,
            l.level_name,
            p.status,
            p.progress_percent,
            p.started_at,
            p.completed_at,
            p.updated_at
        FROM progress p
        JOIN users u ON u.id = p.user_id
        JOIN levels l ON l.id = p.level_id
        """
    )

    cursor.execute("DROP VIEW IF EXISTS user_task_progress_with_usernames")
    cursor.execute(
        """
        CREATE VIEW user_task_progress_with_usernames AS
        SELECT
            utp.id,
            utp.user_id,
            u.username,
            utp.task_id,
            t.task_name,
            t.level_id,
            utp.status,
            utp.attempts,
            utp.best_score,
            utp.last_score,
            utp.last_attempt_at,
            utp.completed_at
        FROM user_task_progress utp
        JOIN users u ON u.id = utp.user_id
        JOIN tasks t ON t.id = utp.task_id
        """
    )

    cursor.execute("DROP VIEW IF EXISTS user_level_progress_with_usernames")
    cursor.execute(
        """
        CREATE VIEW user_level_progress_with_usernames AS
        SELECT
            ulp.id,
            ulp.user_id,
            u.username,
            ulp.level_id,
            l.level_name,
            ulp.status,
            ulp.completed_tasks,
            ulp.total_tasks,
            ulp.attempts,
            ulp.best_score,
            ulp.started_at,
            ulp.completed_at,
            ulp.last_activity_at
        FROM user_level_progress ulp
        JOIN users u ON u.id = ulp.user_id
        JOIN levels l ON l.id = ulp.level_id
        """
    )

    cursor.execute("DROP VIEW IF EXISTS certificates_with_usernames")
    cursor.execute(
        """
        CREATE VIEW certificates_with_usernames AS
        SELECT
            c.id,
            c.user_id,
            u.username,
            c.level_id,
            COALESCE(l.level_name, 'N/A') AS level_name,
            c.cert_ref_id,
            c.certificate_no,
            c.title,
            c.issued_for,
            c.score_snapshot,
            c.completion_date,
            c.created_at
        FROM certificates c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN levels l ON l.id = c.level_id
        """
    )

    cursor.execute("DROP VIEW IF EXISTS practice_sessions_with_usernames")
    cursor.execute(
        """
        CREATE VIEW practice_sessions_with_usernames AS
        SELECT
            ps.id,
            ps.user_id,
            u.username,
            ps.game_type,
            ps.duration_seconds,
            ps.started_at
        FROM practice_sessions ps
        JOIN users u ON u.id = ps.user_id
        """
    )


def seed_levels(cursor):
    levels = [
        (1, 'Level 1', 'Basic Notes', 1, 0),
        (2, 'Level 2', 'Simple Melody', 2, 0),
        (3, 'Level 3', 'Intermediate', 3, 0),
        (4, 'Level 4', 'Final Challenge', 4, 0),
    ]
    cursor.executemany(
        """
        INSERT INTO levels (id, level_name, description, level_order, unlock_score)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            level_name = excluded.level_name,
            description = excluded.description,
            level_order = excluded.level_order,
            unlock_score = excluded.unlock_score,
            updated_at = CURRENT_TIMESTAMP
        """,
        levels,
    )


def seed_tasks(cursor):
    tasks = [
        (1, 1, 'Identify the note C', 'C', 'quiz', 100, 60, 1),
        (2, 1, 'Identify the note D', 'D', 'quiz', 100, 60, 2),
        (3, 1, 'Identify the note E', 'E', 'quiz', 100, 60, 3),
        (4, 2, 'Play Mary Had a Little Lamb intro', 'E D C D E E E', 'practice', 100, 60, 1),
        (5, 2, 'Play Twinkle Twinkle first phrase', 'C C G G A A G', 'practice', 100, 60, 2),
        (6, 2, 'Play Happy Birthday opening', 'C C D C F E', 'practice', 100, 60, 3),
        (7, 3, 'Build the C major chord', 'C E G', 'quiz', 100, 70, 1),
        (8, 3, 'Build the G major chord', 'G B D', 'quiz', 100, 70, 2),
        (9, 3, 'Build the A minor chord', 'A C E', 'quiz', 100, 70, 3),
        (10, 4, 'Play C major scale both hands', 'C D E F G A B C', 'practice', 100, 75, 1),
        (11, 4, 'Play arpeggio C-E-G-C', 'C E G C', 'practice', 100, 75, 2),
        (12, 4, 'Perform progression I-V-vi-IV in C', 'C G Am F', 'practice', 100, 75, 3),
    ]
    cursor.executemany(
        """
        INSERT INTO tasks (
            id, level_id, task_name, correct_answer, task_type, max_score, passing_score, display_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            level_id = excluded.level_id,
            task_name = excluded.task_name,
            correct_answer = excluded.correct_answer,
            task_type = excluded.task_type,
            max_score = excluded.max_score,
            passing_score = excluded.passing_score,
            display_order = excluded.display_order,
            updated_at = CURRENT_TIMESTAMP
        """,
        tasks,
    )


def init_db(app):
    db = sqlite3.connect(_database_path(app))
    _apply_pragmas(db)
    cursor = db.cursor()

    _create_tables(cursor)
    _ensure_backward_compatibility_columns(cursor)
    _backfill_timestamp_columns(cursor)
    _backfill_certificate_reference_ids(cursor)
    _create_indexes(cursor)
    _create_user_lookup_views(cursor)

    seed_user(cursor, 'admin', 'admin123', 'admin')
    seed_user(cursor, 'student', '1234', 'user')
    seed_levels(cursor)
    seed_tasks(cursor)

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


def delete_user_by_username(username):
    db = get_db()
    db.execute("DELETE FROM users WHERE username = ?", (username,))
    db.commit()


def save_progress(user_id, level_id, status):
    normalized_status = status if status in PROGRESS_STATUSES else 'in_progress'
    progress_percent = 100 if normalized_status == 'completed' else 0

    db = get_db()
    db.execute(
        """
        INSERT INTO progress (
            user_id,
            level_id,
            status,
            progress_percent,
            started_at,
            completed_at,
            updated_at
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            CURRENT_TIMESTAMP,
            CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(user_id, level_id) DO UPDATE SET
            status = excluded.status,
            progress_percent = excluded.progress_percent,
            completed_at = CASE
                WHEN excluded.status = 'completed' THEN CURRENT_TIMESTAMP
                ELSE progress.completed_at
            END,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, level_id, normalized_status, progress_percent, normalized_status),
    )

    db.execute(
        """
        INSERT INTO user_level_progress (
            user_id,
            level_id,
            status,
            completed_tasks,
            total_tasks,
            attempts,
            best_score,
            started_at,
            completed_at,
            last_activity_at
        )
        VALUES (
            ?,
            ?,
            ?,
            CASE WHEN ? = 'completed' THEN (SELECT COUNT(*) FROM tasks WHERE level_id = ?) ELSE 0 END,
            (SELECT COUNT(*) FROM tasks WHERE level_id = ?),
            1,
            0,
            CURRENT_TIMESTAMP,
            CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(user_id, level_id) DO UPDATE SET
            status = excluded.status,
            completed_tasks = CASE
                WHEN excluded.status = 'completed' THEN excluded.total_tasks
                ELSE user_level_progress.completed_tasks
            END,
            total_tasks = excluded.total_tasks,
            attempts = user_level_progress.attempts + 1,
            completed_at = CASE
                WHEN excluded.status = 'completed' THEN CURRENT_TIMESTAMP
                ELSE user_level_progress.completed_at
            END,
            last_activity_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            level_id,
            normalized_status,
            normalized_status,
            level_id,
            level_id,
            normalized_status,
        ),
    )

    db.commit()


def add_score(user_id, game_type, score):
    db = get_db()
    db.execute(
        "INSERT INTO scores (user_id, game_type, score, recorded_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (user_id, game_type, score),
    )
    db.commit()


def add_quiz_score(
    user_id,
    score,
    level_id=None,
    task_id=None,
    quiz_name=None,
    total_questions=0,
    correct_answers=0,
    attempt_no=1,
    passed=False,
):
    db = get_db()
    db.execute(
        """
        INSERT INTO quiz_scores (
            user_id,
            level_id,
            task_id,
            quiz_name,
            score,
            total_questions,
            correct_answers,
            attempt_no,
            passed,
            submitted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            user_id,
            level_id,
            task_id,
            quiz_name,
            int(score),
            int(total_questions),
            int(correct_answers),
            max(1, int(attempt_no)),
            1 if bool(passed) else 0,
        ),
    )
    db.commit()


def save_task_progress(user_id, task_id, status='in_progress', last_score=0):
    normalized_status = status if status in PROGRESS_STATUSES else 'in_progress'
    safe_last_score = max(0, int(last_score))
    db = get_db()
    db.execute(
        """
        INSERT INTO user_task_progress (
            user_id,
            task_id,
            status,
            attempts,
            best_score,
            last_score,
            last_attempt_at,
            completed_at
        )
        VALUES (
            ?,
            ?,
            ?,
            1,
            ?,
            ?,
            CURRENT_TIMESTAMP,
            CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END
        )
        ON CONFLICT(user_id, task_id) DO UPDATE SET
            status = excluded.status,
            attempts = user_task_progress.attempts + 1,
            best_score = MAX(user_task_progress.best_score, excluded.last_score),
            last_score = excluded.last_score,
            last_attempt_at = CURRENT_TIMESTAMP,
            completed_at = CASE
                WHEN excluded.status = 'completed' THEN CURRENT_TIMESTAMP
                ELSE user_task_progress.completed_at
            END
        """,
        (user_id, task_id, normalized_status, safe_last_score, safe_last_score, normalized_status),
    )
    db.commit()


def issue_certificate(user_id, level_id=None, issued_for=None, score_snapshot=None):
    db = get_db()
    existing = db.execute(
        """
        SELECT
            id,
            user_id,
            level_id,
            cert_ref_id,
            certificate_no,
            title,
            issued_for,
            score_snapshot,
            completion_date,
            created_at
        FROM certificates
        WHERE user_id = ? AND COALESCE(level_id, -1) = COALESCE(?, -1)
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, level_id),
    ).fetchone()
    if existing is not None:
        return existing

    certificate_no = f"PNV-{user_id}-{level_id or 0}-{db.execute('SELECT COUNT(*) FROM certificates').fetchone()[0] + 1}"
    db.execute(
        """
        INSERT INTO certificates (
            user_id,
            level_id,
            cert_ref_id,
            certificate_no,
            title,
            issued_for,
            score_snapshot,
            completion_date,
            created_at
        )
        VALUES (?, ?, NULL, ?, 'Pianova Completion Certificate', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (user_id, level_id, certificate_no, issued_for, score_snapshot),
    )
    certificate_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    cert_ref_id = f"CERT-{int(certificate_id):06d}"
    db.execute(
        "UPDATE certificates SET cert_ref_id = ? WHERE id = ?",
        (cert_ref_id, certificate_id),
    )
    db.commit()
    return db.execute(
        """
        SELECT
            id,
            user_id,
            level_id,
            cert_ref_id,
            certificate_no,
            title,
            issued_for,
            score_snapshot,
            completion_date,
            created_at
        FROM certificates
        WHERE id = ?
        """,
        (certificate_id,),
    ).fetchone()


def get_latest_certificate_for_user(user_id):
    return get_db().execute(
        """
        SELECT
            id,
            user_id,
            level_id,
            cert_ref_id,
            certificate_no,
            title,
            issued_for,
            score_snapshot,
            completion_date,
            created_at
        FROM certificates
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def add_practice_session(user_id, game_type, duration_seconds):
    db = get_db()
    db.execute(
        """
        INSERT INTO practice_sessions (user_id, game_type, duration_seconds)
        VALUES (?, ?, ?)
        """,
        (user_id, game_type, duration_seconds),
    )
    db.commit()


def _build_level_overview_donut_gradient(level_overview):
    segments = []
    start_angle = 0.0

    visible_levels = [item for item in level_overview if int(item.get('count', 0)) > 0]
    if not visible_levels:
        return 'conic-gradient(#1f2329 0deg 360deg)'

    for index, item in enumerate(visible_levels):
        if index == len(visible_levels) - 1:
            end_angle = 360.0
        else:
            end_angle = start_angle + ((float(item.get('percentage', 0)) / 100.0) * 360.0)

        segments.append(f"{item['color_hex']} {start_angle:.2f}deg {end_angle:.2f}deg")
        start_angle = end_angle

    return f"conic-gradient({', '.join(segments)})"


def get_level_overview():
    db = get_db()
    total_users = db.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'user'"
    ).fetchone()[0]

    level_rows = db.execute(
        """
        SELECT id, level_name, level_order
        FROM levels
        ORDER BY level_order ASC
        """
    ).fetchall()

    if not level_rows:
        return {
            'levels': [],
            'donut_gradient': 'conic-gradient(#1f2329 0deg 360deg)',
            'total_users': total_users,
        }

    level_counts = db.execute(
        """
        WITH user_highest AS (
            SELECT
                u.id AS user_id,
                COALESCE(MAX(l.level_order), 1) AS highest_level_order
            FROM users u
            LEFT JOIN progress p
                ON p.user_id = u.id
                AND p.status = 'completed'
            LEFT JOIN levels l
                ON l.id = p.level_id
            WHERE u.role = 'user'
            GROUP BY u.id
        )
        SELECT
            lv.id AS level_id,
            COUNT(uh.user_id) AS user_count
        FROM levels lv
        LEFT JOIN user_highest uh
            ON uh.highest_level_order = lv.level_order
        GROUP BY lv.id
        ORDER BY lv.level_order ASC
        """
    ).fetchall()

    count_by_level_id = {
        int(row['level_id']): int(row['user_count'])
        for row in level_counts
    }

    color_tokens = [
        ('purple', '#6c2db5'),
        ('blue', '#1760ca'),
        ('green', '#2d9743'),
        ('orange', '#f39212'),
    ]

    level_overview = []
    for index, level in enumerate(level_rows):
        color_class, color_hex = color_tokens[index % len(color_tokens)]
        count = count_by_level_id.get(int(level['id']), 0)
        percentage = round((count / total_users) * 100.0, 1) if total_users else 0.0
        level_overview.append(
            {
                'level_name': level['level_name'],
                'count': count,
                'percentage': percentage,
                'color_class': color_class,
                'color_hex': color_hex,
            }
        )

    return {
        'levels': level_overview,
        'donut_gradient': _build_level_overview_donut_gradient(level_overview),
        'total_users': total_users,
    }


def get_admin_metrics():
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
    total_admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    total_scores = db.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    total_certificates = db.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
    completed_lessons = db.execute(
        "SELECT COUNT(*) FROM progress WHERE status = 'completed'"
    ).fetchone()[0]
    recent_students_week = db.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE role = 'user'
          AND created_at IS NOT NULL
          AND datetime(created_at) >= datetime('now', '-7 days')
        """
    ).fetchone()[0]
    recent_users = db.execute(
        "SELECT username, role FROM users ORDER BY id DESC LIMIT 5"
    ).fetchall()
    level_overview = get_level_overview()
    return {
        'total_users': total_users,
        'total_admins': total_admins,
        'total_scores': total_scores,
        'total_certificates': total_certificates,
        'completed_lessons': completed_lessons,
        'recent_students_week': recent_students_week,
        'recent_users': recent_users,
        'level_overview': level_overview['levels'],
        'level_overview_donut': level_overview['donut_gradient'],
    }


def get_all_accounts():
    return get_db().execute(
        "SELECT id, username, password, role, created_at FROM users ORDER BY id DESC"
    ).fetchall()


def get_registered_users():
    return get_db().execute(
        """
        SELECT id, username, password, role, created_at
        FROM users
        WHERE role = 'user'
        ORDER BY id DESC
        """
    ).fetchall()


def get_recent_scores(limit=25):
    return get_db().execute(
        """
        SELECT
            s.id,
            u.username,
            s.game_type,
            s.score
        FROM scores s
        JOIN users u ON u.id = s.user_id
        ORDER BY s.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_recent_progress(limit=25):
    return get_db().execute(
        """
        SELECT
            p.id,
            u.username,
            l.level_name,
            p.status
        FROM progress p
        JOIN users u ON u.id = p.user_id
        JOIN levels l ON l.id = p.level_id
        ORDER BY p.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_recent_certificates(limit=25):
    return get_db().execute(
        """
        SELECT
            c.id,
            c.cert_ref_id,
            c.certificate_no,
            u.username,
            COALESCE(l.level_name, 'N/A') AS level_name,
            c.completion_date
        FROM certificates c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN levels l ON l.id = c.level_id
        ORDER BY c.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_certificate_account_by_ref(cert_ref_id):
    normalized_ref = (cert_ref_id or '').strip()
    if not normalized_ref:
        return None

    return get_db().execute(
        """
        SELECT
            c.id,
            c.cert_ref_id,
            c.certificate_no,
            c.completion_date,
            c.level_id,
            u.id AS user_id,
            u.username,
            u.role,
            COALESCE(l.level_name, 'N/A') AS level_name
        FROM certificates c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN levels l ON l.id = c.level_id
        WHERE UPPER(c.cert_ref_id) = UPPER(?)
        LIMIT 1
        """,
        (normalized_ref,),
    ).fetchone()


def get_weekly_practice_hours(user_id, days=7):
    safe_days = max(1, min(int(days), 30))
    db = get_db()
    lower_bound = f'-{safe_days - 1} days'

    rows = db.execute(
        """
        SELECT DATE(started_at) AS session_date, COALESCE(SUM(duration_seconds), 0) AS total_seconds
        FROM practice_sessions
        WHERE user_id = ?
          AND DATE(started_at) >= DATE('now', ?)
        GROUP BY DATE(started_at)
        """,
        (user_id, lower_bound),
    ).fetchall()

    totals_by_date = {row['session_date']: int(row['total_seconds']) for row in rows}
    today = date.today()
    points = []

    for offset in range(safe_days - 1, -1, -1):
        day_value = today - timedelta(days=offset)
        day_key = day_value.isoformat()
        seconds = totals_by_date.get(day_key, 0)
        points.append(
            {
                'label': day_value.strftime('%a'),
                'date': day_key,
                'seconds': seconds,
                'hours': round(seconds / 3600.0, 2),
            }
        )

    return points


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
    practice_seconds = db.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM practice_sessions WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    return {
        'score_total': score_total,
        'completed_lessons': completed,
        'current_level': current_level,
        'practice_seconds': practice_seconds,
    }


def get_completed_level_ids(user_id):
    db = get_db()
    rows = db.execute(
        """
        SELECT level_id
        FROM progress
        WHERE user_id = ? AND status = 'completed'
        ORDER BY level_id ASC
        """,
        (user_id,),
    ).fetchall()
    return [int(row['level_id']) for row in rows]


if __name__ == "__main__":
    print("Run the Flask app to initialize the database.")