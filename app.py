from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(_name_)
app.secret_key = "secretkey"


# 🔹 Connect to YOUR database
def connect_db():
    conn = sqlite3.connect("pianova.db")
    conn.row_factory = sqlite3.Row
    return conn


# 🔹 LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = connect_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect("/admin")
            else:
                return redirect("/user")
        else:
            return "Invalid username or password"

    return render_template("login.html")


# 🔹 ADMIN DASHBOARD
@app.route("/admin")
def admin():
    if session.get("role") == "admin":
        return render_template("admin_dashboard.html")
    return redirect("/")


# 🔹 USER DASHBOARD
@app.route("/user")
def user():
    if session.get("role") == "user":
        return render_template("user_dashboard.html")
    return redirect("/")


# 🔹 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if _name_ == "_main_":
    app.run(debug=True)