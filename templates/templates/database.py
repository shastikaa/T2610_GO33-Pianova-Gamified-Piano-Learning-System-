import sqlite3

# 🔹 Connect to database
def connect_db():
    conn = sqlite3.connect("pianova.db")
    return conn


# 🔹 Create all tables
def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    # 👤 USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # 🎮 LEVELS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_name TEXT NOT NULL,
        description TEXT
    )
    """)

    # 📝 TASKS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_id INTEGER,
        task_name TEXT,
        correct_answer TEXT,
        FOREIGN KEY (level_id) REFERENCES levels(id)
    )
    """)

    # 🎯 SCORES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        game_type TEXT,
        score INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # 📊 PROGRESS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        level_id INTEGER,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (level_id) REFERENCES levels(id)
    )
    """)

    # 🏆 CERTIFICATES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        completion_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


# 🔹 Insert default data
def insert_data():
    conn = connect_db()
    cursor = conn.cursor()

    # 👨‍💻 ADMIN
    cursor.execute("""
    INSERT OR IGNORE INTO users (id, username, password, role)
    VALUES (1, 'admin', 'admin123', 'admin')
    """)

    # 👤 SAMPLE USER
    cursor.execute("""
    INSERT OR IGNORE INTO users (id, username, password, role)
    VALUES (2, 'student', '1234', 'user')
    """)

    # 🎮 LEVELS
    cursor.execute("INSERT OR IGNORE INTO levels (id, level_name, description) VALUES (1, 'Level 1', 'Basic Notes')")
    cursor.execute("INSERT OR IGNORE INTO levels (id, level_name, description) VALUES (2, 'Level 2', 'Simple Melody')")
    cursor.execute("INSERT OR IGNORE INTO levels (id, level_name, description) VALUES (3, 'Level 3', 'Intermediate')")
    cursor.execute("INSERT OR IGNORE INTO levels (id, level_name, description) VALUES (4, 'Level 4', 'Final Challenge')")

    conn.commit()
    conn.close()


# 🔹 Run everything
if __name__ == "__main__":
    create_tables()
    insert_data()
    print("✅ Pianova Database Created Successfully!")