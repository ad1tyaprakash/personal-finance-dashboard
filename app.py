from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import yfinance as yf
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "your_super_secret_key"

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

def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return round(stock.info["regularMarketPrice"], 2)
    except Exception:
        return None

def fetch_popular_stocks():
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NFLX", "NVDA", "META", "INTC", "ADBE"]
    dropdown_options = []
    for symbol in symbols:
        try:
            stock = yf.Ticker(symbol)
            name = stock.info.get("shortName") or symbol
            dropdown_options.append((symbol, name))
        except:
            continue
    return dropdown_options

@app.route("/")
def index():
    return render_template("index.html", active_page="home")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if not username or not password:
            flash("Username and password are required!", "danger")
            return redirect("/register")
        conn = get_db_connection()
        existing_user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
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
        username = request.form["username"]
        password = request.form["password"]
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

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()

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

@app.route("/add_stock", methods=["POST"])
@login_required
def add_stock():
    ticker = request.form["ticker"].upper()
    quantity = int(request.form["quantity"])
    purchase_price = float(request.form["purchase_price"])
    conn = get_db_connection()
    conn.execute("INSERT INTO stocks (user_id, ticker, quantity, purchase_price) VALUES (?, ?, ?, ?)",
                 (session["user_id"], ticker, quantity, purchase_price))
    conn.commit()
    conn.close()
    flash(f"Added {quantity} shares of {ticker}", "success")
    return redirect("/dashboard")

@app.route("/add_income", methods=["POST"])
@login_required
def add_income():
    source = request.form["source"]
    amount = float(request.form["amount"])
    date = request.form["date"]
    conn = get_db_connection()
    conn.execute("INSERT INTO income (user_id, source, amount, date) VALUES (?, ?, ?, ?)",
                 (session["user_id"], source, amount, date))
    conn.commit()
    conn.close()
    flash("Income added.", "success")
    return redirect("/dashboard")

@app.route("/add_expense", methods=["POST"])
@login_required
def add_expense():
    category = request.form["category"]
    amount = float(request.form["amount"])
    date = request.form["date"]
    conn = get_db_connection()
    conn.execute("INSERT INTO expenses (user_id, category, amount, date) VALUES (?, ?, ?, ?)",
                 (session["user_id"], category, amount, date))
    conn.commit()
    conn.close()
    flash("Expense added.", "danger")
    return redirect("/dashboard")

@app.route("/add_savings", methods=["POST"])
@login_required
def add_savings():
    savings_type = request.form["type"]
    amount = float(request.form["amount"])
    conn = get_db_connection()
    conn.execute("INSERT INTO savings (user_id, type, amount) VALUES (?, ?, ?)",
                 (session["user_id"], savings_type, amount))
    conn.commit()
    conn.close()
    flash("Savings added.", "primary")
    return redirect("/dashboard")

@app.route("/view_profile", methods=["POST"])
@login_required
def view_profile() :
    
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
