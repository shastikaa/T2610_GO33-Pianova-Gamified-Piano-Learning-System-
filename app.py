from flask import Flask, render_template, redirect, url_for, session, request

app = Flask(__name__, static_folder='static')
app.secret_key = "secret123"

# HOME PAGE
@app.route('/')
def home():
    return render_template('templates/index.html')

# LESSON PAGE
@app.route('/lessons')
def lessons():
    if 'user' not in session:
        return redirect(url_for('login'))

    # default progress
    if 'level' not in session:
        session['level'] = 1

    return render_template('lessons.html', level=session['level'])


# GAME PAGE
@app.route('/game', methods=['GET', 'POST'])
def game():
    if 'user' not in session:
        return redirect(url_for('login'))

    message = ""

    if request.method == 'POST':
        answer = request.form['note']

        if answer == 'C':
            message = "Correct ✅"
            session['level'] = 2   # unlock next level
        else:
            message = "Wrong ❌ Try again"

    return render_template('game.html', message=message)


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True) 
    