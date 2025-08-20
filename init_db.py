import sqlite3
from werkzeug.security import generate_password_hash

def init():
    conn = sqlite3.connect("finance.db")
    c = conn.cursor()
    # users
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        hash TEXT NOT NULL
    )
    """)
    # income, expenses, savings
    c.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        source TEXT,
        amount REAL,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        amount REAL,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS savings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # stocks owned
    c.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ticker TEXT,
        quantity REAL,
        purchase_price REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # watchlist
    c.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        ticker TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # debts
    c.execute("""
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        creditor TEXT,
        amount REAL,
        interest_rate REAL,
        monthly_payment REAL,
        due_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # generic transactions / statement
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        description TEXT,
        date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    # sample user if none exist
    cur = c.execute("SELECT count(*) FROM users").fetchone()[0]
    if cur == 0:
        pw = generate_password_hash("password")
        c.execute("INSERT INTO users (username, hash) VALUES (?, ?)", ("demo", pw))
    conn.commit()
    conn.close()
    print("Initialized finance.db")

if __name__ == "__main__":
    init()