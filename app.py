from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from sqlalchemy import text

from helpers import db, get_db_session, login_required, get_user_by_id, get_current_price, fetch_popular_stocks

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_super_secret_key")

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
        s = get_db_session()
        existing_user = s.execute(text("SELECT id FROM users WHERE username = :username"), {"username": username}).mappings().fetchone()
        if existing_user:
            flash("Username already exists.", "warning")
            return redirect("/register")
        hash_pw = generate_password_hash(password)
        s.execute(text("INSERT INTO users (username, hash) VALUES (:username, :hash)"),
                  {"username": username, "hash": hash_pw})
        s.commit()
        flash("Registered successfully. Please log in.", "success")
        return redirect("/login")
    return render_template("register.html", active_page="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        s = get_db_session()
        user = s.execute(text("SELECT * FROM users WHERE username = :username"), {"username": username}).mappings().fetchone()
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
    s = get_db_session()

    expenses_rows = s.execute(
        text("SELECT category, SUM(amount) as total FROM expenses WHERE user_id = :uid GROUP BY category"),
        {"uid": session["user_id"]}
    ).mappings().fetchall()
    labels = [str(row["category"] or "") for row in expenses_rows]
    data = [float(row["total"]) if row["total"] is not None else 0.0 for row in expenses_rows]

    total_income = s.execute(
        text("SELECT SUM(amount) FROM income WHERE user_id = :uid"), {"uid": session["user_id"]}
    ).scalar() or 0
    total_expense = s.execute(
        text("SELECT SUM(amount) FROM expenses WHERE user_id = :uid"), {"uid": session["user_id"]}
    ).scalar() or 0
    deficit = round(total_income - total_expense, 2)

    total_savings = s.execute(
        text("SELECT SUM(amount) FROM savings WHERE user_id = :uid"), {"uid": session["user_id"]}
    ).scalar() or 0

    stocks = s.execute(text("SELECT * FROM stocks WHERE user_id = :uid"), {"uid": session["user_id"]}).mappings().fetchall()
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

    return render_template("dashboard.html",
        username=session.get("username"),
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
    s = get_db_session()
    ticker = request.form.get("ticker", "").upper().strip()
    try:
        quantity = float(request.form.get("quantity", "0") or 0)
    except ValueError:
        quantity = 0
    try:
        purchase_price = float(request.form.get("purchase_price", "0") or 0)
    except ValueError:
        purchase_price = 0
    if not ticker or quantity <= 0 or purchase_price < 0:
        flash("Invalid stock input.", "danger")
        return redirect("/dashboard")
    s.execute(
        text("INSERT INTO stocks (user_id, ticker, quantity, purchase_price) VALUES (:uid, :ticker, :qty, :price)"),
        {"uid": session["user_id"], "ticker": ticker, "qty": quantity, "price": purchase_price}
    )
    s.commit()
    flash(f"Added {ticker} ({quantity} @ {purchase_price})", "success")
    return redirect("/dashboard")

@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    s = get_db_session()
    if request.method == "POST":
        ticker = request.form.get("ticker", "").upper().strip()
        if ticker:
            s.execute(text("INSERT INTO watchlist (user_id, ticker) VALUES (:uid, :ticker)"),
                      {"uid": session["user_id"], "ticker": ticker})
            s.commit()
            flash(f"Added {ticker} to watchlist", "success")
        return redirect("/watchlist")
    items = s.execute(text("SELECT * FROM watchlist WHERE user_id = :uid"), {"uid": session["user_id"]}).mappings().fetchall()
    resolved = []
    for it in items:
        price = get_current_price(it["ticker"]) or "N/A"
        resolved.append({"id": it["id"], "ticker": it["ticker"], "price": price})
    return render_template("watchlist.html", items=resolved, active_page="watchlist")

@app.route("/watchlist/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_watchlist(item_id):
    s = get_db_session()
    s.execute(text("DELETE FROM watchlist WHERE id = :id AND user_id = :uid"), {"id": item_id, "uid": session["user_id"]})
    s.commit()
    flash("Removed from watchlist", "info")
    return redirect("/watchlist")

@app.route("/debts", methods=["GET", "POST"])
@login_required
def debts():
    s = get_db_session()
    if request.method == "POST":
        creditor = request.form.get("creditor")
        amount = float(request.form.get("amount") or 0)
        interest = float(request.form.get("interest") or 0)
        monthly = float(request.form.get("monthly_payment") or 0)
        due_date = request.form.get("due_date") or None
        s.execute(text("INSERT INTO debts (user_id, creditor, amount, interest_rate, monthly_payment, due_date) VALUES (:uid, :creditor, :amount, :interest, :monthly, :due)"),
                  {"uid": session["user_id"], "creditor": creditor, "amount": amount, "interest": interest, "monthly": monthly, "due": due_date})
        s.commit()
        flash("Debt added.", "success")
        return redirect("/debts")
    rows = s.execute(text("SELECT * FROM debts WHERE user_id = :uid"), {"uid": session["user_id"]}).mappings().fetchall()
    return render_template("debts.html", debts=rows, active_page="debts")

@app.route("/debts/remove/<int:debt_id>", methods=["POST"])
@login_required
def remove_debt(debt_id):
    s = get_db_session()
    s.execute(text("DELETE FROM debts WHERE id = :id AND user_id = :uid"), {"id": debt_id, "uid": session["user_id"]})
    s.commit()
    flash("Debt removed.", "info")
    return redirect("/debts")

@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    s = get_db_session()
    if request.method == "POST":
        t_type = request.form.get("type")
        amount = float(request.form.get("amount") or 0)
        description = request.form.get("description")
        date = request.form.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
        s.execute(text("INSERT INTO transactions (user_id, type, amount, description, date) VALUES (:uid, :type, :amount, :desc, :date)"),
                  {"uid": session["user_id"], "type": t_type, "amount": amount, "desc": description, "date": date})
        s.commit()
        flash("Transaction logged.", "success")
        return redirect("/transactions")
    start = request.args.get("start")
    end = request.args.get("end")
    q = "SELECT * FROM transactions WHERE user_id = :uid"
    params = {"uid": session["user_id"]}
    if start:
        q += " AND date >= :start"; params["start"] = start
    if end:
        q += " AND date <= :end"; params["end"] = end
    q += " ORDER BY date DESC"
    rows = s.execute(text(q), params).mappings().fetchall()
    return render_template("transactions.html", transactions=rows, active_page="transactions")

@app.route("/api/price")
@login_required
def api_price():
    ticker = request.args.get("ticker", "").upper()
    price = get_current_price(ticker)
    return jsonify({"ticker": ticker, "price": price})

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    s = get_db_session()
    user = s.execute(text("SELECT id, username FROM users WHERE id = :id"), {"id": session["user_id"]}).mappings().fetchone()
    if request.method == "POST":
        newname = request.form.get("username").strip()
        if newname:
            s.execute(text("UPDATE users SET username = :username WHERE id = :id"), {"username": newname, "id": session["user_id"]})
            s.commit()
            session["username"] = newname
            flash("Profile updated.", "success")
            return redirect("/profile")
    return render_template("profile.html", user=user, active_page="profile")

@app.route("/add_income", methods=["POST"])
@login_required
def add_income():
    s = get_db_session()
    source = request.form.get("source", "").strip()
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0
    date = request.form.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
    if not source or amount <= 0:
        flash("Invalid income input.", "danger")
        return redirect("/dashboard")
    s.execute(
        text("INSERT INTO income (user_id, source, amount, date) VALUES (:uid, :source, :amount, :date)"),
        {"uid": session["user_id"], "source": source, "amount": amount, "date": date}
    )
    s.commit()
    flash("Income added.", "success")
    return redirect("/dashboard")

@app.route("/add_expense", methods=["POST"])
@login_required
def add_expense():
    s = get_db_session()
    category = request.form.get("category", "").strip()
    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0
    date = request.form.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
    if not category or amount <= 0:
        flash("Invalid expense input.", "danger")
        return redirect("/dashboard")
    s.execute(
        text("INSERT INTO expenses (user_id, category, amount, date) VALUES (:uid, :category, :amount, :date)"),
        {"uid": session["user_id"], "category": category, "amount": amount, "date": date}
    )
    s.commit()
    flash("Expense added.", "success")
    return redirect("/dashboard")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
