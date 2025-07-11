from functools import wraps
from flask import redirect, session
import sqlite3
import yfinance as yf


def get_db_connection():
    conn = sqlite3.connect("finance.db")
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_current_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        return round(stock.info["regularMarketPrice"], 2)
    except Exception:
        return None
