from functools import wraps
from flask import redirect, session
import os
import yfinance as yf
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

# Use DATABASE_URL env var (set in Render). Fallback to the external Render URL for local dev.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://finance_jmfn_user:dDvFG0bNmVLZsR7y0vdo4nq8VfEhr5MF@dpg-d2ipkmjuibrs73a4hg9g-a.oregon-postgres.render.com/finance_jmfn"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
db = scoped_session(sessionmaker(bind=engine))

def get_db_session():
    return db

def close_db_session():
    db.remove()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_id(user_id):
    s = get_db_session()
    return s.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).mappings().fetchone()

def get_current_price(symbol):
    """Return current market price for symbol or None on failure."""
    try:
        stock = yf.Ticker(symbol)
        info = getattr(stock, "info", {}) or {}
        price = info.get("regularMarketPrice") or info.get("previousClose")
        if price is None:
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist["Close"].iloc[-1]
        return round(float(price), 2) if price is not None else None
    except Exception:
        return None

def fetch_popular_stocks():
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

# --- Auto-create tables on startup (idempotent) ---
DDL = """
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS income (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  source TEXT,
  amount DOUBLE PRECISION,
  date DATE
);

CREATE TABLE IF NOT EXISTS expenses (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  category TEXT,
  amount DOUBLE PRECISION,
  date DATE
);

CREATE TABLE IF NOT EXISTS savings (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  type TEXT,
  amount DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS stocks (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  ticker TEXT,
  quantity DOUBLE PRECISION,
  purchase_price DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS watchlist (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  ticker TEXT
);

CREATE TABLE IF NOT EXISTS debts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  creditor TEXT,
  amount DOUBLE PRECISION,
  interest_rate DOUBLE PRECISION,
  monthly_payment DOUBLE PRECISION,
  due_date DATE
);

CREATE TABLE IF NOT EXISTS transactions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  type TEXT,
  amount DOUBLE PRECISION,
  description TEXT,
  date DATE
);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(DDL))
except Exception:
    # don't crash import if DB unavailable at import time (Render will provide DATABASE_URL at runtime)
    pass
