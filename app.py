from functools import wraps
import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from templates.templates.database import (
    add_quiz_score,
    add_score,
    add_practice_session,
    create_user,
    fetch_user_by_username,
    get_all_accounts,
    get_admin_metrics,
    get_latest_certificate_for_user,
    get_recent_progress,
    get_recent_scores,
    get_user_metrics,
    init_app as init_database_app,
    init_db,
    issue_certificate,
    reset_password,
    save_progress,
    save_task_progress,
)

app = Flask(__name__, static_folder='static')
app.secret_key = "secret123"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
init_database_app(app)


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def verify_password(stored_password, provided_password):
    if stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:'):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password


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


def build_progress_chart(metrics):
    labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    completed_lessons = int(metrics.get('completed_lessons', 0))
    total_score = int(metrics.get('score_total', 0))
    current_level = int(metrics.get('current_level', 1))

    progress_ratio = min(completed_lessons / 12.0, 1.0)
    score_ratio = min(total_score / 200.0, 1.0)
    level_ratio = min(max(current_level - 1, 0) / 3.0, 1.0)
    overall_progress = (progress_ratio * 0.52) + (score_ratio * 0.28) + (level_ratio * 0.20)

    shape = [0.22, 0.46, 0.34, 0.58, 0.82, 0.60, 0.40]
    points = []

    for index, label in enumerate(labels):
        day_factor = index / 6.0
        wave = shape[index]
        value = 16 + (overall_progress * 64) + (completed_lessons * day_factor * 2.1) + (current_level * 2.5)
        value = value * wave
        value = max(12, min(92, round(value)))
        points.append({'label': label, 'value': value})

    return points


def build_progress_chart_geometry(points, width=860, height=220, left=40, top=28, right=40, bottom=26):
    if not points:
        return {'path': '', 'fill_path': '', 'dots': []}

    chart_width = width - left - right
    chart_height = height - top - bottom
    step = chart_width / (len(points) - 1 if len(points) > 1 else 1)

    dots = []
    path_parts = []
    fill_parts = []

    for index, point in enumerate(points):
        x = left + (step * index)
        y = top + (chart_height * (1 - (point['value'] / 100.0)))
        dots.append({
            'label': point['label'],
            'value': point['value'],
            'x': round(x, 1),
            'y': round(y, 1),
        })

    for index, dot in enumerate(dots):
        if index == 0:
            path_parts.append(f"M {dot['x']} {dot['y']}")
            fill_parts.append(f"M {dot['x']} {height - bottom}")
            fill_parts.append(f"L {dot['x']} {dot['y']}")
        else:
            previous = dots[index - 1]
            mid_x = round((previous['x'] + dot['x']) / 2, 1)
            path_parts.append(f"C {mid_x} {previous['y']}, {mid_x} {dot['y']}, {dot['x']} {dot['y']}")
            fill_parts.append(f"C {mid_x} {previous['y']}, {mid_x} {dot['y']}, {dot['x']} {dot['y']}")

    fill_parts.append(f"L {dots[-1]['x']} {height - bottom}")
    fill_parts.append(f"L {dots[0]['x']} {height - bottom}")
    fill_parts.append('Z')

    return {
        'path': ' '.join(path_parts),
        'fill_path': ' '.join(fill_parts),
        'dots': dots,
    }


def format_practice_time(metrics):
    total_seconds = int(metrics.get('practice_seconds', 0))
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f'{hours}h {minutes}m'
    return f'{minutes}m'


def build_next_lesson_card(current_level):
    lessons = {
        1: {
            'label': 'Lesson 1',
            'title': 'Getting Started',
            'description': 'Learn the basics of music notes and finger position.',
            'button_text': 'Continue',
        },
        2: {
            'label': 'Lesson 2',
            'title': 'Basic Notes',
            'description': 'Practice simple melodies and note recognition.',
            'button_text': 'Continue',
        },
        3: {
            'label': 'Lesson 3',
            'title': 'Chords',
            'description': 'Build chords and strengthen your hand coordination.',
            'button_text': 'Continue',
        },
        4: {
            'label': 'Lesson 4',
            'title': 'Advanced Practice',
            'description': 'Push your speed and accuracy with harder patterns.',
            'button_text': 'Continue',
        },
    }
    return lessons.get(current_level, lessons[4])


def practice_href_for_level(current_level):
    return url_for('game2') if current_level >= 2 else url_for('game')


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
            return render_template('login.html')

        session.clear()
        session['user_id'] = user['id']
        session['user'] = user['username']
        session['role'] = user['role']
        session['level'] = 1

        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))

    return render_template('login.html')


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

        create_user(username, generate_password_hash(password), 'user')

        flash('Account created. You can log in now.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not new_password:
            flash('All fields are required.', 'error')
            return render_template('forgot_password.html')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('forgot_password.html')

        if len(new_password) < 4:
            flash('Password must be at least 4 characters.', 'error')
            return render_template('forgot_password.html')

        user = fetch_user_by_username(username)
        if user is None:
            flash('No account found with that username.', 'error')
            return render_template('forgot_password.html')

        reset_password(username, generate_password_hash(new_password))
        flash('Password reset successfully. You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('forgot_password.html')


@app.route('/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    metrics = get_user_metrics(session['user_id'], session.get('level', 1))
    current_level = int(metrics.get('current_level', 1))
    return render_template(
        'user_dashboard.html',
        username=session['user'],
        metrics=metrics,
        progress_chart=build_progress_chart_geometry(build_progress_chart(metrics)),
        practice_time=format_practice_time(metrics),
        practice_href=practice_href_for_level(current_level),
        next_lesson=build_next_lesson_card(current_level),
    )


@app.route('/admin-dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    return render_template(
        'admin_dashboard.html',
        username=session['user'],
        metrics=get_admin_metrics(),
        accounts=get_all_accounts(),
        recent_scores=get_recent_scores(),
        recent_progress=get_recent_progress(),
    )


@app.route('/lessons')
@login_required
@role_required('user')
def lessons():
    session['level'] = max(session.get('level', 1), 1)
    return render_template('templates/index.html', level=session['level'])


@app.route('/game', methods=['GET', 'POST'])
@app.route('/game1', methods=['GET'])
@login_required
@role_required('user')
def game():
    return render_template('templates/game1.html')


@app.route('/game2', methods=['GET'])
@login_required
@role_required('user')
def game2():
    return render_template('game2.html')


@app.route('/lesson2-1', methods=['GET'])
@login_required
@role_required('user')
def lesson2_1():
    return render_template('level2(lesson1)')


@app.route('/lesson2-2', methods=['GET'])
@login_required
@role_required('user')
def lesson2_2():
    return render_template('level 2(lesson 2).html')


@app.route('/lesson2-4', methods=['GET'])
@login_required
@role_required('user')
def lesson2_4():
    return render_template('level 2(lesson 4).html')


@app.route('/level1-lesson2', methods=['GET'])
@login_required
@role_required('user')
def level1_lesson2():
    return render_template('level2(lesson1)')


@app.route('/lesson2-1-latest', methods=['GET'])
@login_required
@role_required('user')
def lesson2_1_latest():
    return render_template('level2(lesson1)')


@app.route('/level2-lesson1', methods=['GET'])
@login_required
@role_required('user')
def level2_lesson1_alias():
    return render_template('level2(lesson1)')


@app.route('/level2-lesson4', methods=['GET'])
@login_required
@role_required('user')
def level2_lesson4_alias():
    return render_template('level 2(lesson 4).html')


@app.route('/api/save-game2', methods=['POST'])
@login_required
@role_required('user')
def save_game2():
    data = request.get_json(silent=True) or {}

    try:
        score = int(data.get('score', 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 1000))

    raw_passed = data.get('passed', False)
    if isinstance(raw_passed, bool):
        passed = raw_passed
    else:
        passed = str(raw_passed).strip().lower() in {'1', 'true', 'yes', 'y'}

    try:
        total_questions = int(data.get('total_questions', 10))
    except (TypeError, ValueError):
        total_questions = 10
    total_questions = max(1, min(total_questions, 1000))
    correct_answers = max(0, min(score, total_questions))

    user_id = session['user_id']

    add_score(user_id, 'game2', score)
    add_quiz_score(
        user_id=user_id,
        level_id=2,
        task_id=4,
        quiz_name='Game 2 Staff Notes Challenge',
        score=score,
        total_questions=total_questions,
        correct_answers=correct_answers,
        attempt_no=1,
        passed=passed,
    )
    save_task_progress(user_id, task_id=4, status='completed' if passed else 'in_progress', last_score=score)

    certificate = None
    if passed:
        save_progress(user_id, 2, 'completed')
        session['level'] = max(int(session.get('level', 1)), 2)
        certificate = issue_certificate(
            user_id=user_id,
            level_id=2,
            issued_for=session.get('user'),
            score_snapshot=score,
        )

    return {
        'status': 'ok',
        'passed': passed,
        'certificate_issued': certificate is not None,
        'certificate_no': certificate['certificate_no'] if certificate else None,
        'certificate_url': url_for('certificate_page') if certificate else None,
    }


@app.route('/certificate', methods=['GET'])
@login_required
@role_required('user')
def certificate_page():
    certificate = get_latest_certificate_for_user(session['user_id'])
    return render_template(
        'certificate.html',
        username=session.get('user', 'Student'),
        certificate=certificate,
    )


@app.route('/api/log-practice-session', methods=['POST'])
@login_required
@role_required('user')
def log_practice_session():
    data = request.get_json(silent=True) or {}
    game_type = str(data.get('game_type', 'practice'))[:32]
    try:
        duration_seconds = int(float(data.get('duration_seconds', 0)))
    except (TypeError, ValueError):
        duration_seconds = 0

    duration_seconds = max(0, min(duration_seconds, 24 * 60 * 60))
    if duration_seconds > 0:
        add_practice_session(session['user_id'], game_type, duration_seconds)

    return {'status': 'ok'}


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


init_db(app)


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', '5000')),
        debug=True,
    )
