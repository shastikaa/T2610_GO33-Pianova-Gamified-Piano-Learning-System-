from functools import wraps
import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from templates.templates.database import (
    add_score,
    create_user,
    fetch_user_by_username,
    get_all_accounts,
    get_admin_metrics,
    get_user_metrics,
    init_app as init_database_app,
    init_db,
    reset_password,
    save_progress,
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
    return render_template(
        'user_dashboard.html',
        username=session['user'],
        metrics=get_user_metrics(session['user_id'], session.get('level', 1)),
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
