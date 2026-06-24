from functools import wraps
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from hashlib import sha256

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
    get_certificate_account_by_ref,
    get_completed_level_ids,
    get_latest_certificate_for_user,
    get_recent_certificates,
    get_recent_progress,
    get_recent_scores,
    get_registered_users,
    get_user_metrics,
    get_weekly_practice_hours,
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
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
init_database_app(app)

# Dedicated admin login credentials. You can override with environment variables.
ADMIN_LOGIN_USERNAME = os.getenv('PIANOVA_ADMIN_USERNAME', 'admin')
ADMIN_LOGIN_PASSWORD = os.getenv('PIANOVA_ADMIN_PASSWORD', 'admin123')

EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
AUTH_CODE_TTL_SECONDS = int(os.getenv('PIANOVA_AUTH_CODE_TTL_SECONDS', '300'))
AUTH_CODE_RESEND_SECONDS = int(os.getenv('PIANOVA_AUTH_CODE_RESEND_SECONDS', '30'))
AUTH_CODE_MAX_ATTEMPTS = int(os.getenv('PIANOVA_AUTH_CODE_MAX_ATTEMPTS', '5'))
ALLOW_LOCAL_OTP_FALLBACK = str(os.getenv('PIANOVA_ALLOW_LOCAL_OTP_FALLBACK', 'false')).strip().lower() in {
    '1',
    'true',
    'yes',
}

# In-memory auth code store. For production scale, move this to Redis/database.
auth_code_store = {}


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    # Allow the auth APIs to be called from local preview origins (including file://).
    if request.path.startswith('/api/auth/'):
        origin = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Origin'] = '*' if origin == 'null' else origin
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

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


def build_practice_time_points(hours_by_day):
    points = []
    max_hours = 0.0

    for item in hours_by_day:
        hours = max(0.0, float(item.get('hours', 0.0)))
        max_hours = max(max_hours, hours)
        points.append({'label': item.get('label', ''), 'hours': hours})

    # Keep tiny sessions visible: if user practiced only a few minutes,
    # we still want the chart to rise instead of appearing flat.
    scale_max = max(0.05, max_hours)

    for point in points:
        if point['hours'] <= 0:
            point['value'] = 0.0
            continue

        raw_value = (point['hours'] / scale_max) * 100.0
        point['value'] = round(max(14.0, min(100.0, raw_value)), 2)

    return points, scale_max


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
    return format_duration_seconds(total_seconds)


def format_duration_seconds(total_seconds):
    total_seconds = int(total_seconds)
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


def continue_lesson_href_for_level(current_level):
    if current_level <= 1:
        return url_for('game')
    if current_level == 2:
        return url_for('lesson2_1_latest')
    return url_for('game2')


def level_label(current_level):
    if current_level <= 1:
        return 'Beginner 🎵'
    if current_level == 2:
        return 'Young Pianist 🎵'
    if current_level == 3:
        return 'Intermediate 🎶'
    return 'Advanced 🌟'


def normalize_email(value):
    return value.strip().lower()


def is_valid_email(value):
    return bool(EMAIL_REGEX.match(value))


def hash_auth_code(code):
    return sha256(code.encode('utf-8')).hexdigest()


def generate_auth_code():
    return f'{secrets.randbelow(1000000):06d}'


def send_verification_email(recipient_email, code):
    smtp_host = os.getenv('PIANOVA_SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('PIANOVA_SMTP_PORT', '465'))
    smtp_user = os.getenv('PIANOVA_SMTP_USER', '').strip()
    # Gmail app passwords are often shown with spaces for readability.
    # Remove all spaces so both "abcd efgh ijkl mnop" and "abcdefghijklmnop" work.
    smtp_password = os.getenv('PIANOVA_SMTP_PASSWORD', '').strip().replace(' ', '')
    smtp_from = os.getenv('PIANOVA_SMTP_FROM', smtp_user).strip()

    if not smtp_user or not smtp_password or not smtp_from:
        raise RuntimeError(
            'SMTP is not configured. Set PIANOVA_SMTP_USER, PIANOVA_SMTP_PASSWORD, and PIANOVA_SMTP_FROM.'
        )

    message = EmailMessage()
    message['Subject'] = 'Pianova Verification Code'
    message['From'] = smtp_from
    message['To'] = recipient_email
    message.set_content(
        (
            'Welcome to Pianova!\n\n'
            f'Your verification code is: {code}\n\n'
            f'This code expires in {AUTH_CODE_TTL_SECONDS // 60} minutes.\n'
            'If you did not request this, please ignore this email.'
        )
    )

    use_tls = str(os.getenv('PIANOVA_SMTP_USE_TLS', 'false')).strip().lower() in {'1', 'true', 'yes'}

    if use_tls:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20, context=ssl.create_default_context()) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def cleanup_expired_auth_codes(now_ts):
    expired_emails = [
        email
        for email, entry in auth_code_store.items()
        if now_ts - float(entry.get('created_at', 0)) > AUTH_CODE_TTL_SECONDS
    ]
    for email in expired_emails:
        auth_code_store.pop(email, None)


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

        # Only this dedicated username/password should open admin dashboard.
        if username == ADMIN_LOGIN_USERNAME and password == ADMIN_LOGIN_PASSWORD:
            admin_user = fetch_user_by_username(ADMIN_LOGIN_USERNAME)
            if admin_user is None:
                create_user(ADMIN_LOGIN_USERNAME, generate_password_hash(ADMIN_LOGIN_PASSWORD), 'admin')
                admin_user = fetch_user_by_username(ADMIN_LOGIN_USERNAME)

            if admin_user is None:
                flash('Admin login is temporarily unavailable.', 'error')
                return render_template('login.html')

            session.clear()
            session['user_id'] = admin_user['id']
            session['user'] = admin_user['username']
            session['role'] = 'admin'
            session['level'] = 1
            return redirect(url_for('admin_dashboard'))

        user = fetch_user_by_username(username)
        if user is None or not verify_password(user['password'], password):
            flash('Invalid username or password.', 'error')
            return render_template('login.html')

        session.clear()
        session['user_id'] = user['id']
        session['user'] = user['username']
        session['role'] = 'user'
        session['level'] = 1
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
        created_user = fetch_user_by_username(username)

        if created_user is None:
            flash('Account was created but sign-in failed. Please log in manually.', 'error')
            return redirect(url_for('login'))

        session.clear()
        session['user_id'] = created_user['id']
        session['user'] = created_user['username']
        session['role'] = 'user'
        session['level'] = 1

        flash('Account created successfully.', 'success')
        return redirect(url_for('user_dashboard'))

    return render_template('register.html')


@app.route('/register-auth', methods=['GET'])
def register_auth_page():
    return render_template('sirajcode.html')


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


@app.route('/api/auth/send-code', methods=['POST'])
def send_auth_code_api():
    data = request.get_json(silent=True) or {}
    raw_email = str(data.get('email', '')).strip()

    if not raw_email:
        return {'message': 'Email is required.'}, 400

    email = normalize_email(raw_email)
    if not is_valid_email(email):
        return {'message': 'Invalid email format.'}, 400

    now_ts = time.time()
    cleanup_expired_auth_codes(now_ts)

    existing_entry = auth_code_store.get(email)
    if existing_entry is not None:
        elapsed = now_ts - float(existing_entry.get('created_at', 0))
        if elapsed < AUTH_CODE_RESEND_SECONDS:
            retry_in = int(AUTH_CODE_RESEND_SECONDS - elapsed)
            return {'message': f'Please wait {retry_in}s before requesting another code.'}, 429

    code = generate_auth_code()
    auth_code_store[email] = {
        'code_hash': hash_auth_code(code),
        'created_at': now_ts,
        'attempts': 0,
    }

    try:
        send_verification_email(email, code)
    except Exception as error:
        error_text = str(error)
        is_local_request = request.host.startswith('127.0.0.1') or request.host.startswith('localhost')

        # Local development fallback: keep OTP active and return it only in debug mode.
        if ALLOW_LOCAL_OTP_FALLBACK and (app.debug or is_local_request) and 'SMTP is not configured' in error_text:
            return {
                'message': 'SMTP is not configured. Using local OTP fallback for development.',
                'debug_otp': code,
            }

        auth_code_store.pop(email, None)
        return {'message': f'Email send failed: {error}'}, 500

    return {'message': 'Verification code sent successfully.'}


@app.route('/api/auth/verify-code', methods=['POST'])
def verify_auth_code_api():
    data = request.get_json(silent=True) or {}
    raw_email = str(data.get('email', '')).strip()
    code = str(data.get('code', '')).strip()

    if not raw_email or not code:
        return {'message': 'Email and verification code are required.'}, 400

    email = normalize_email(raw_email)
    if not is_valid_email(email):
        return {'message': 'Invalid email format.'}, 400

    now_ts = time.time()
    cleanup_expired_auth_codes(now_ts)
    entry = auth_code_store.get(email)

    if entry is None:
        return {'message': 'Verification code not found or expired.'}, 400

    age_seconds = now_ts - float(entry.get('created_at', 0))
    if age_seconds > AUTH_CODE_TTL_SECONDS:
        auth_code_store.pop(email, None)
        return {'message': 'Verification code expired. Please request a new one.'}, 400

    entry['attempts'] = int(entry.get('attempts', 0)) + 1
    if entry['attempts'] > AUTH_CODE_MAX_ATTEMPTS:
        auth_code_store.pop(email, None)
        return {'message': 'Too many failed attempts. Request a new code.'}, 429

    if hash_auth_code(code) != entry.get('code_hash'):
        return {'message': 'Invalid verification code.'}, 400

    auth_code_store.pop(email, None)
    session['verified_email'] = email
    session['verified_at'] = int(now_ts)

    return {'message': 'Email verified successfully.'}


@app.route('/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    metrics = get_user_metrics(session['user_id'], session.get('level', 1))
    current_level = int(metrics.get('current_level', 1))
    weekly_practice = get_weekly_practice_hours(session['user_id'])
    practice_points, practice_scale_max = build_practice_time_points(weekly_practice)
    weekly_seconds = sum(int(item.get('seconds', 0)) for item in weekly_practice)

    return render_template(
        'user_dashboard.html',
        username=session['user'],
        metrics=metrics,
        progress_chart=build_progress_chart_geometry(practice_points),
        practice_chart_max_hours=round(practice_scale_max, 2),
        practice_hours_week=round(weekly_seconds / 3600.0, 1),
        weekly_practice_time=format_duration_seconds(weekly_seconds),
        practice_time=format_practice_time(metrics),
        current_level_label=level_label(current_level),
        lessons_card_url=url_for('lessons'),
        practice_href=practice_href_for_level(current_level),
        next_lesson=build_next_lesson_card(current_level),
    )


@app.route('/api/current-user', methods=['GET'])
@login_required
@role_required('user')
def current_user_api():
    username = session.get('user', 'Student')
    return {
        'username': username,
        'initial': (username[:1].upper() if username else 'S'),
    }


@app.route('/api/weekly-practice', methods=['GET'])
@login_required
@role_required('user')
def weekly_practice_api():
    weekly_practice = get_weekly_practice_hours(session['user_id'])
    practice_points, practice_scale_max = build_practice_time_points(weekly_practice)
    weekly_seconds = sum(int(item.get('seconds', 0)) for item in weekly_practice)
    chart = build_progress_chart_geometry(practice_points)

    return {
        'weekly_practice_time': format_duration_seconds(weekly_seconds),
        'total_practice_time': format_duration_seconds(
            get_user_metrics(session['user_id'], session.get('level', 1)).get('practice_seconds', 0)
        ),
        'chart': chart,
        'scale_max_hours': round(practice_scale_max, 2),
    }


@app.route('/admin-dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    cert_ref_id = request.args.get('cert_ref_id', '').strip()
    certificate_lookup = None

    if cert_ref_id:
        certificate_lookup = get_certificate_account_by_ref(cert_ref_id)

    return render_template(
        'admindash.html',
        username=session['user'],
        metrics=get_admin_metrics(),
        accounts=get_registered_users(),
        recent_scores=get_recent_scores(),
        recent_progress=get_recent_progress(),
        recent_certificates=get_recent_certificates(),
        cert_ref_id=cert_ref_id,
        certificate_lookup=certificate_lookup,
    )


@app.route('/admin-users')
@login_required
@role_required('admin')
def admin_users():
    return render_template(
        'templates/admindash_users.html',
        username=session['user'],
        metrics=get_admin_metrics(),
        accounts=get_registered_users(),
    )


@app.route('/admin-certificates')
@login_required
@role_required('admin')
def admin_certificates():
    return render_template(
        'admindash_certificate.html',
        username=session['user'],
        metrics=get_admin_metrics(),
        certificates=get_recent_certificates(limit=500),
    )


@app.route('/lessons')
@login_required
@role_required('user')
def lessons():
    session['level'] = max(session.get('level', 1), 1)
    completed_levels = get_completed_level_ids(session['user_id'])
    return render_template(
        'templates/index.html',
        level=session['level'],
        completed_levels=completed_levels,
    )


@app.route('/game', methods=['GET', 'POST'])
@login_required
@role_required('user')
def game():
    return render_template('templates/game1.html')


@app.route('/game1', methods=['GET'])
@login_required
@role_required('user')
def game1_entry():
    return render_template('templates/level1(lesson1).html')


@app.route('/level1-notes', methods=['GET'])
@login_required
@role_required('user')
def level1_notes():
    return render_template('templates/game1.html')


@app.route('/game2', methods=['GET'])
@login_required
@role_required('user')
def game2():
    # Legacy endpoint fallback: route old game2 entry to level4 part1.
    return render_template('level4(part1).html')


@app.route('/level1-lesson1', methods=['GET'])
@login_required
@role_required('user')
def level1_lesson1():
    return render_template('templates/level1(lesson1).html')


@app.route('/level1-lesson1exercise', methods=['GET'])
@login_required
@role_required('user')
def level1_lesson1exercise():
    return render_template('templates/level1(lesson1exercise).html')


@app.route('/lesson2-1', methods=['GET'])
@login_required
@role_required('user')
def lesson2_1():
    return render_template('level2(lesson 1).html')


@app.route('/lesson2-2', methods=['GET'])
@login_required
@role_required('user')
def lesson2_2():
    return render_template('level 2(lesson 2).html')


@app.route('/lesson2-3', methods=['GET'])
@app.route('/level2-lesson3', methods=['GET'])
@login_required
@role_required('user')
def lesson2_3():
    lesson3_template = 'level2(lesson 3).html'
    lesson3_path = os.path.join(app.root_path, 'templates', lesson3_template)
    if os.path.exists(lesson3_path):
        return render_template(lesson3_template)
    return render_template('level 2(lesson 4).html')


@app.route('/level2', methods=['GET'])
@login_required
@role_required('user')
def level2_home():
    return render_template('level2.html')


@app.route('/lesson2-4', methods=['GET'])
@login_required
@role_required('user')
def lesson2_4():
    return render_template('level 2(lesson 4).html')


@app.route('/level1-lesson2', methods=['GET'])
@login_required
@role_required('user')
def level1_lesson2():
    return render_template('level2(lesson 1).html')


@app.route('/lesson2-1-latest', methods=['GET'])
@login_required
@role_required('user')
def lesson2_1_latest():
    return render_template('level2(lesson 1).html')


@app.route('/level2-lesson1', methods=['GET'])
@login_required
@role_required('user')
def level2_lesson1_alias():
    return render_template('level2(lesson 1).html')


@app.route('/level2-lesson4', methods=['GET'])
@login_required
@role_required('user')
def level2_lesson4_alias():
    return render_template('level 2(lesson 4).html')


@app.route('/lesson3-1', methods=['GET'])
@login_required
@role_required('user')
def lesson3_1():
    return render_template('level3(lesson1).html')


@app.route('/lesson3-2', methods=['GET'])
@login_required
@role_required('user')
def lesson3_2():
    return render_template('level3(lesson2).html')


@app.route('/lesson3-3', methods=['GET'])
@login_required
@role_required('user')
def lesson3_3():
    return render_template('level3(lesson3).html')


@app.route('/lesson3-4', methods=['GET'])
@login_required
@role_required('user')
def lesson3_4():
    return render_template('level3(lesson4).html')


@app.route('/lesson3-5', methods=['GET'])
@app.route('/level3(lesson5).html', methods=['GET'])
@app.route('/level3(lesson5).html.html', methods=['GET'])
@login_required
@role_required('user')
def lesson3_5():
    return render_template('level3(lesson5).html')


@app.route('/lesson3-6', methods=['GET'])
@app.route('/level3(lesson6).html', methods=['GET'])
@app.route('/level3(lesson6).html.html', methods=['GET'])
@login_required
@role_required('user')
def lesson3_6():
    return render_template('level3(lesson6).html')


@app.route('/level4', methods=['GET'])
@app.route('/level4-part1', methods=['GET'])
@app.route('/game4', methods=['GET'])
@app.route('/level4.html', methods=['GET'])
@login_required
@role_required('user')
def level4():
    return render_template('level4(part1).html')


@app.route('/level4-part2', methods=['GET'])
@app.route('/level4(part2).html', methods=['GET'])
@login_required
@role_required('user')
def level4_part2():
    return render_template('level4(part2).html')


@app.route('/level4-part3', methods=['GET'])
@app.route('/level4(part3).html', methods=['GET'])
@login_required
@role_required('user')
def level4_part3():
    return render_template('level4(part3).html')


@app.route('/precertificatepage', methods=['GET'])
@app.route('/precertificatepage.html', methods=['GET'])
@app.route('/precertificate.html', methods=['GET'])
@login_required
@role_required('user')
def precertificate_page():
    return render_template('precertificatepage.html')


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

    if passed:
        save_progress(user_id, 2, 'completed')
        session['level'] = max(int(session.get('level', 1)), 2)

    return {
        'status': 'ok',
        'passed': passed,
        'certificate_issued': False,
        'certificate_no': None,
        'certificate_url': None,
    }


@app.route('/api/complete-level1', methods=['POST'])
@login_required
@role_required('user')
def complete_level1():
    data = request.get_json(silent=True) or {}

    try:
        score = int(data.get('score', 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 1000))

    user_id = session['user_id']
    save_progress(user_id, 1, 'completed')
    save_task_progress(user_id, task_id=1, status='completed', last_score=score)
    session['level'] = max(int(session.get('level', 1)), 1)

    return {
        'status': 'ok',
        'level_completed': True,
        'certificate_issued': False,
        'certificate_no': None,
        'certificate_url': None,
    }


@app.route('/api/complete-level3', methods=['POST'])
@login_required
@role_required('user')
def complete_level3():
    data = request.get_json(silent=True) or {}

    try:
        score = int(data.get('score', 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 1000))

    user_id = session['user_id']
    save_progress(user_id, 3, 'completed')
    session['level'] = max(int(session.get('level', 1)), 3)

    return {
        'status': 'ok',
        'level_completed': True,
        'certificate_issued': False,
        'certificate_no': None,
        'certificate_url': None,
    }


@app.route('/api/complete-level4', methods=['POST'])
@login_required
@role_required('user')
def complete_level4():
    data = request.get_json(silent=True) or {}

    try:
        score = int(data.get('score', 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 1000))

    user_id = session['user_id']

    save_progress(user_id, 4, 'completed')
    save_task_progress(user_id, task_id=10, status='completed', last_score=score)
    session['level'] = max(int(session.get('level', 1)), 4)

    certificate = issue_certificate(
        user_id=user_id,
        level_id=4,
        issued_for=session.get('user'),
        score_snapshot=score,
    )

    return {
        'status': 'ok',
        'level_completed': True,
        'certificate_issued': certificate is not None,
        'certificate_no': certificate['certificate_no'] if certificate else None,
        'certificate_url': url_for('certificate_page'),
    }


@app.route('/certificate', methods=['GET'])
@login_required
@role_required('user')
def certificate_page():
    certificate = get_latest_certificate_for_user(session['user_id'])
    issued_for = session.get('user', 'Student')
    certificate_title = 'Beginner Piano Course'

    if certificate is not None:
        raw_issued_for = (certificate['issued_for'] or '').strip()
        raw_certificate_title = (certificate['title'] or '').strip()

        # Ignore placeholder-like values stored in old records.
        if raw_issued_for and not (raw_issued_for.startswith('{{') and raw_issued_for.endswith('}}')):
            issued_for = raw_issued_for

        if raw_certificate_title and not (raw_certificate_title.startswith('{{') and raw_certificate_title.endswith('}}')):
            certificate_title = raw_certificate_title

    return render_template(
        'certificate.html',
        username=session.get('user', 'Student'),
        certificate=certificate,
        issued_for=issued_for,
        certificate_title=certificate_title,
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
