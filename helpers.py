from functools import wraps
from flask import redirect, session
import sqlite3
import yfinance as yf


def get_db_connection():
    conn = sqlite3.connect("finance.db", detect_types=sqlite3.PARSE_DECLTYPES)
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
    """Return current market price for symbol or None on failure."""
    try:
        stock = yf.Ticker(symbol)
        price = None
        # primary: info dict
        info = getattr(stock, "info", {}) or {}
        price = info.get("regularMarketPrice") or info.get("previousClose")
        # fallback: recent history
        if price is None:
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
        return round(float(price), 2) if price is not None else None
    except Exception:
        return None

def fetch_popular_stocks():
    """Return list of (symbol, shortName) for common tickers."""
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NFLX", "NVDA", "META", "INTC", "ADBE"]
    dropdown_options = []
    for symbol in symbols:
        name = symbol
        try:
            stock = yf.Ticker(symbol)
            info = getattr(stock, "info", {}) or {}
            name = info.get("shortName") or symbol
        except Exception:
            pass
        dropdown_options.append((symbol, name))
    return dropdown_options
