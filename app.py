from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import yfinance as yf
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_super_secret_key")

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

def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.info.get("regularMarketPrice")
        if price is None:
            # fallback to history
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
            name = stock.info.get("shortName") or symbol
        except Exception:
            pass
        dropdown_options.append((symbol, name))
    return dropdown_options

@app.route("/")
def index():
    return render_template("index.html", active_page="home")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required!", "danger")
            return redirect("/register")
        conn = get_db_connection()
        existing_user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
            conn.close()
            flash("Username already exists.", "warning")
            return redirect("/register")
        hash_pw = generate_password_hash(password)
        conn.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hash_pw))
        conn.commit()
        conn.close()
        flash("Registered successfully. Please log in.", "success")
        return redirect("/login")
    return render_template("register.html", active_page="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user is None or not check_password_hash(user["hash"], password):
            flash("Invalid username or password.", "danger")
            return redirect("/login")
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash("Logged in successfully!", "success")
        return redirect("/dashboard")
    return render_template("login.html", active_page="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    # expenses by category
    expenses = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category",
        (session["user_id"],)
    ).fetchall()
    labels = [row["category"] for row in expenses]
    data = [row["total"] for row in expenses]

    total_income = conn.execute("SELECT SUM(amount) FROM income WHERE user_id = ?", (session["user_id"],)).fetchone()[0] or 0
    total_expense = conn.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (session["user_id"],)).fetchone()[0] or 0
    deficit = round(total_income - total_expense, 2)

    total_savings = conn.execute("SELECT SUM(amount) FROM savings WHERE user_id = ?", (session["user_id"],)).fetchone()[0] or 0

    stocks = conn.execute("SELECT * FROM stocks WHERE user_id = ?", (session["user_id"],)).fetchall()
    total_stock_value = 0
    stock_data = []
    for stock in stocks:
        current_price = get_current_price(stock["ticker"]) or 0
        current_value = round(current_price * stock["quantity"], 2)
        profit = round(current_value - (stock["quantity"] * stock["purchase_price"]), 2)
        total_stock_value += current_value
        stock_data.append({
            "ticker": stock["ticker"],
            "quantity": stock["quantity"],
            "purchase_price": stock["purchase_price"],
            "current_price": current_price,
            "current_value": current_value,
            "profit": profit
        })

    total_net_worth = round(total_savings + total_stock_value, 2)

    conn.close()
    return render_template("dashboard.html",
        username=session["username"],
        labels=labels,
        data=data,
        stock_data=stock_data,
        available_stocks=fetch_popular_stocks(),
        net_worth=total_stock_value,
        total_savings=total_savings,
        total_net_worth=total_net_worth,
        deficit=deficit,
        active_page="dashboard"
    )

# Watchlist routes
@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    conn = get_db_connection()
    if request.method == "POST":
        ticker = request.form.get("ticker", "").upper().strip()
        if ticker:
            conn.execute("INSERT INTO watchlist (user_id, ticker) VALUES (?, ?)", (session["user_id"], ticker))
            conn.commit()
            flash(f"Added {ticker} to watchlist", "success")
        return redirect("/watchlist")
    items = conn.execute("SELECT * FROM watchlist WHERE user_id = ?", (session["user_id"],)).fetchall()
    conn.close()
    # resolve current prices
    resolved = []
    for it in items:
        price = get_current_price(it["ticker"]) or "N/A"
        resolved.append({"id": it["id"], "ticker": it["ticker"], "price": price})
    return render_template("watchlist.html", items=resolved, active_page="watchlist")

@app.route("/watchlist/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_watchlist(item_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM watchlist WHERE id = ? AND user_id = ?", (item_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Removed from watchlist", "info")
    return redirect("/watchlist")

# Debts
@app.route("/debts", methods=["GET", "POST"])
@login_required
def debts():
    conn = get_db_connection()
    if request.method == "POST":
        creditor = request.form.get("creditor")
        amount = float(request.form.get("amount") or 0)
        interest = float(request.form.get("interest") or 0)
        monthly = float(request.form.get("monthly_payment") or 0)
        due_date = request.form.get("due_date") or None
        conn.execute(
            "INSERT INTO debts (user_id, creditor, amount, interest_rate, monthly_payment, due_date) VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_id"], creditor, amount, interest, monthly, due_date)
        )
        conn.commit()
        flash("Debt added.", "success")
        return redirect("/debts")
    rows = conn.execute("SELECT * FROM debts WHERE user_id = ?", (session["user_id"],)).fetchall()
    conn.close()
    return render_template("debts.html", debts=rows, active_page="debts")

@app.route("/debts/remove/<int:debt_id>", methods=["POST"])
@login_required
def remove_debt(debt_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM debts WHERE id = ? AND user_id = ?", (debt_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Debt removed.", "info")
    return redirect("/debts")

# Transactions and statements
@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    conn = get_db_connection()
    if request.method == "POST":
        t_type = request.form.get("type")
        amount = float(request.form.get("amount") or 0)
        description = request.form.get("description")
        date = request.form.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
        conn.execute("INSERT INTO transactions (user_id, type, amount, description, date) VALUES (?, ?, ?, ?, ?)",
                     (session["user_id"], t_type, amount, description, date))
        conn.commit()
        flash("Transaction logged.", "success")
        return redirect("/transactions")
    # optional filtering
    start = request.args.get("start")
    end = request.args.get("end")
    q = "SELECT * FROM transactions WHERE user_id = ?"
    params = [session["user_id"]]
    if start:
        q += " AND date >= ?"; params.append(start)
    if end:
        q += " AND date <= ?"; params.append(end)
    q += " ORDER BY date DESC"
    rows = conn.execute(q, tuple(params)).fetchall()
    conn.close()
    return render_template("transactions.html", transactions=rows, active_page="transactions")

# API: get price for ticker (ajax)
@app.route("/api/price")
@login_required
def api_price():
    ticker = request.args.get("ticker", "").upper()
    price = get_current_price(ticker)
    return jsonify({"ticker": ticker, "price": price})

# profile view/edit
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db_connection()
    user = conn.execute("SELECT id, username FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        newname = request.form.get("username").strip()
        if newname:
            conn.execute("UPDATE users SET username = ? WHERE id = ?", (newname, session["user_id"]))
            conn.commit()
            session["username"] = newname
            flash("Profile updated.", "success")
            return redirect("/profile")
    conn.close()
    return render_template("profile.html", user=user, active_page="profile")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
