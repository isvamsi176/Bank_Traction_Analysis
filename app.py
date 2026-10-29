from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
import csv
import os
import sqlite3

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import Flask, flash, redirect, render_template, request, send_file, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FINSIGHT_DB", os.path.join(BASE_DIR, "finsight.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "finsight-demo-change-me")

ALLOWED_TYPES = {"Deposit", "Withdrawal"}
CURRENCY = "₹"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            account_type TEXT NOT NULL CHECK(account_type IN ('Savings','Current','Student')),
            opening_balance REAL NOT NULL DEFAULT 0 CHECK(opening_balance >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
        );
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            transaction_date TEXT NOT NULL,
            transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Deposit','Withdrawal')),
            amount REAL NOT NULL CHECK(amount > 0),
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES accounts(account_id)
        );
        """)


def seed_demo_data():
    """Ensure the local demo has 100 synthetic customers and 1,000 transactions.

    This is additive and safe to run on every startup: existing user-entered data
    is preserved, and only missing demo rows are added.
    """
    base_names = [
        "Aarav Sharma", "Diya Reddy", "Kabir Mehta", "Ananya Iyer",
        "Ishaan Rao", "Meera Nair", "Vivaan Patel", "Saanvi Gupta",
        "Arjun Kumar", "Aadhya Verma", "Reyansh Singh", "Kiara Das",
        "Advik Joshi", "Anika Menon", "Krish Malhotra", "Myra Shah",
        "Rohan Kapoor", "Ira Choudhary", "Dev Mishra", "Tara Bansal",
        "Aditya Rao", "Navya Reddy", "Vihaan Kulkarni", "Sara Thomas",
        "Neil Fernandes", "Pihu Agarwal", "Atharv Jain", "Riya Banerjee",
        "Dhruv Sinha", "Ishita Pillai", "Karan Gill", "Mira Krishnan",
        "Yash Desai", "Nisha Shetty", "Om Prakash", "Kavya Nambiar",
        "Samar Khan", "Aanya Bose", "Manav Arora", "Zoya Ali"
    ]
    account_types = ["Savings", "Student", "Current"]
    opening_balances = [12500, 8400, 27300, 6100, 18500, 9200, 33600, 7400,
                        15200, 19800, 11400, 22100, 9600, 30500, 12800, 17500]
    descriptions = {
        "Deposit": ["Salary credit", "Monthly savings", "Scholarship credit", "Cash deposit", "Refund received", "Interest credit"],
        "Withdrawal": ["Utility payment", "Grocery purchase", "Transport expense", "Online payment", "ATM withdrawal", "Bill payment"]
    }
    with get_db() as db:
        customer_count = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        while customer_count < 100:
            idx = customer_count
            name = base_names[idx] if idx < len(base_names) else f"Demo Customer {idx + 1:03d}"
            # Avoid duplicate names if the database already contains part of this sample.
            if db.execute("SELECT 1 FROM customers WHERE display_name=?", (name,)).fetchone():
                name = f"Demo Customer {idx + 1:03d}"
            cur = db.execute("INSERT INTO customers(display_name) VALUES (?)", (name,))
            customer_id = cur.lastrowid
            account_type = account_types[idx % len(account_types)]
            opening = float(opening_balances[idx % len(opening_balances)])
            db.execute(
                "INSERT INTO accounts(customer_id, account_type, opening_balance) VALUES (?,?,?)",
                (customer_id, account_type, opening)
            )
            customer_count += 1

        # Add enough synthetic transactions to reach 1,000 total. Existing rows
        # remain untouched; missing rows are distributed across available accounts.
        transaction_count = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        accounts = db.execute("SELECT account_id FROM accounts ORDER BY account_id").fetchall()
        account_ids = [row[0] for row in accounts]
        i = 0
        while transaction_count < 1000 and account_ids:
            account_id = account_ids[i % len(account_ids)]
            customer_idx = i % 100
            tx_date = date.today() - timedelta(days=(i * 7 + customer_idx * 3) % 365)
            tx_type = "Deposit" if i % 3 != 0 else "Withdrawal"
            amount = float([450, 1200, 850, 2200, 700, 1600, 950, 3400, 580, 1250, 2750, 5100][i % 12])
            # Include a few clearly synthetic high-value examples for the review queue.
            if i % 97 == 0:
                amount = 18500.0
            desc_list = descriptions[tx_type]
            description = "Synthetic demo: " + desc_list[i % len(desc_list)]
            db.execute(
                "INSERT INTO transactions(account_id, transaction_date, transaction_type, amount, description) VALUES (?,?,?,?,?)",
                (account_id, tx_date.isoformat(), tx_type, amount, description)
            )
            transaction_count += 1
            i += 1


def fetch_transactions():
    with get_db() as db:
        rows = db.execute("""
            SELECT t.transaction_id, t.account_id, t.transaction_date, t.transaction_type,
                   t.amount, t.description, a.account_type, a.opening_balance,
                   c.display_name, c.customer_id
            FROM transactions t
            JOIN accounts a ON a.account_id=t.account_id
            JOIN customers c ON c.customer_id=a.customer_id
            ORDER BY t.transaction_date DESC, t.transaction_id DESC
        """).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def fetch_accounts():
    with get_db() as db:
        rows = db.execute("""
            SELECT a.account_id, a.customer_id, a.account_type, a.opening_balance,
                   c.display_name,
                   COALESCE(SUM(CASE WHEN t.transaction_type='Deposit' THEN t.amount ELSE 0 END),0) AS deposits,
                   COALESCE(SUM(CASE WHEN t.transaction_type='Withdrawal' THEN t.amount ELSE 0 END),0) AS withdrawals,
                   COUNT(t.transaction_id) AS transaction_count
            FROM accounts a JOIN customers c ON c.customer_id=a.customer_id
            LEFT JOIN transactions t ON t.account_id=a.account_id
            GROUP BY a.account_id
            ORDER BY a.account_id DESC
        """).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["balance"] = float(item["opening_balance"]) + float(item["deposits"]) - float(item["withdrawals"])
        out.append(item)
    return out


def review_flags(df):
    if df.empty:
        return []
    flags = []
    df = df.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    # Transparent educational rules only. These are review prompts, not fraud findings.
    for _, row in df.iterrows():
        reasons = []
        if row["amount"] >= 10000:
            reasons.append("High-value transaction (₹10,000 or more)")
        flags.append({
            "transaction_id": int(row["transaction_id"]),
            "account_id": int(row["account_id"]),
            "display_name": row["display_name"],
            "date": row["transaction_date"],
            "type": row["transaction_type"],
            "amount": float(row["amount"]),
            "description": row.get("description", ""),
            "reasons": reasons
        }) if reasons else None
    df["day"] = df["transaction_date"].astype(str)
    daily_counts = df.groupby(["account_id", "day"]).size()
    busy_days = set((int(a), str(d)) for (a, d), n in daily_counts.items() if n >= 4)
    existing = {f["transaction_id"] for f in flags}
    for _, row in df.iterrows():
        key = (int(row["account_id"]), str(row["transaction_date"]))
        if key in busy_days and int(row["transaction_id"]) not in existing:
            flags.append({
                "transaction_id": int(row["transaction_id"]),
                "account_id": int(row["account_id"]),
                "display_name": row["display_name"],
                "date": row["transaction_date"],
                "type": row["transaction_type"],
                "amount": float(row["amount"]),
                "description": row.get("description", ""),
                "reasons": ["Four or more transactions on the same account and day"]
            })
        elif key in busy_days and int(row["transaction_id"]) in existing:
            for f in flags:
                if f["transaction_id"] == int(row["transaction_id"]):
                    f["reasons"].append("Four or more transactions on the same account and day")
                    break
    return sorted(flags, key=lambda x: (x["date"], x["amount"]), reverse=True)


def money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"


app.jinja_env.filters["money"] = money


@app.route("/")
def dashboard():
    df = fetch_transactions()
    accounts = fetch_accounts()
    with get_db() as db:
        customers_count = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if df.empty:
        deposits = withdrawals = total_volume = 0
    else:
        deposits = float(df.loc[df.transaction_type == "Deposit", "amount"].sum())
        withdrawals = float(df.loc[df.transaction_type == "Withdrawal", "amount"].sum())
        total_volume = float(df.amount.sum())
    total_balance = sum(a["balance"] for a in accounts)
    flags = review_flags(df)
    monthly = []
    if not df.empty:
        df["month"] = pd.to_datetime(df["transaction_date"]).dt.to_period("M").astype(str)
        grouped = df.pivot_table(index="month", columns="transaction_type", values="amount",
                                 aggfunc="sum", fill_value=0).reset_index()
        for _, row in grouped.tail(6).iterrows():
            monthly.append({"month": row["month"], "deposits": float(row.get("Deposit", 0)),
                            "withdrawals": float(row.get("Withdrawal", 0))})
    recent = df.head(8).to_dict("records") if not df.empty else []
    return render_template("dashboard.html", title="Overview", customers_count=customers_count,
        accounts_count=len(accounts), transactions_count=len(df), deposits=deposits,
        withdrawals=withdrawals, total_volume=total_volume, total_balance=total_balance,
        flags_count=len(flags), monthly=monthly, recent=recent, accounts=accounts[:5])


@app.route("/transactions")
def transactions():
    df = fetch_transactions()
    q = request.args.get("q", "").strip().lower()
    typ = request.args.get("type", "")
    account_id = request.args.get("account_id", "")
    if not df.empty:
        if q:
            mask = (df["display_name"].str.lower().str.contains(q, na=False) |
                    df["description"].fillna("").str.lower().str.contains(q, na=False) |
                    df["transaction_id"].astype(str).str.contains(q, na=False))
            df = df[mask]
        if typ in ALLOWED_TYPES:
            df = df[df["transaction_type"] == typ]
        if account_id.isdigit():
            df = df[df["account_id"] == int(account_id)]
    return render_template("transactions.html", title="Transactions",
        transactions=df.to_dict("records"), accounts=fetch_accounts(), q=q, selected_type=typ,
        selected_account=account_id)


@app.route("/transactions/new", methods=["POST"])
def new_transaction():
    account_id = request.form.get("account_id", "")
    typ = request.form.get("transaction_type", "")
    amount_raw = request.form.get("amount", "").strip()
    tx_date = request.form.get("transaction_date", "")
    description = request.form.get("description", "").strip()[:180]
    try:
        amount = float(amount_raw)
        if not np.isfinite(amount) or amount <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid transaction amount greater than zero.", "error")
        return redirect(url_for("transactions"))
    if typ not in ALLOWED_TYPES:
        flash("Choose Deposit or Withdrawal.", "error")
        return redirect(url_for("transactions"))
    try:
        datetime.strptime(tx_date, "%Y-%m-%d")
    except ValueError:
        flash("Choose a valid transaction date.", "error")
        return redirect(url_for("transactions"))
    with get_db() as db:
        account = db.execute("SELECT account_id FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if not account:
            flash("Select a valid account.", "error")
            return redirect(url_for("transactions"))
        db.execute("""INSERT INTO transactions
            (account_id, transaction_date, transaction_type, amount, description)
            VALUES (?,?,?,?,?)""", (int(account_id), tx_date, typ, amount, description))
    flash(f"{typ} recorded in the educational simulation.", "success")
    return redirect(url_for("transactions"))


@app.route("/customers", methods=["GET", "POST"])
def customers():
    if request.method == "POST":
        name = request.form.get("display_name", "").strip()
        account_type = request.form.get("account_type", "Savings")
        opening_raw = request.form.get("opening_balance", "0")
        try:
            opening = float(opening_raw)
            if not np.isfinite(opening) or opening < 0:
                raise ValueError
        except ValueError:
            flash("Opening balance must be zero or greater.", "error")
            return redirect(url_for("customers"))
        if not name or len(name) > 80:
            flash("Enter a display name up to 80 characters.", "error")
            return redirect(url_for("customers"))
        if account_type not in {"Savings", "Current", "Student"}:
            flash("Choose a valid account type.", "error")
            return redirect(url_for("customers"))
        with get_db() as db:
            cur = db.execute("INSERT INTO customers(display_name) VALUES (?)", (name,))
            db.execute("INSERT INTO accounts(customer_id, account_type, opening_balance) VALUES (?,?,?)",
                       (cur.lastrowid, account_type, opening))
        flash("Synthetic customer and account created.", "success")
        return redirect(url_for("customers"))
    with get_db() as db:
        rows = db.execute("""
            SELECT c.customer_id,c.display_name,c.created_at,COUNT(a.account_id) AS account_count
            FROM customers c LEFT JOIN accounts a ON a.customer_id=c.customer_id
            GROUP BY c.customer_id ORDER BY c.customer_id DESC
        """).fetchall()
    return render_template("customers.html", title="Customers", customers=[dict(r) for r in rows])


@app.route("/accounts")
def accounts():
    return render_template("accounts.html", title="Accounts", accounts=fetch_accounts())


@app.route("/analytics")
def analytics():
    df = fetch_transactions()
    monthly = []
    by_type = {"Deposit": 0, "Withdrawal": 0}
    stats = {"mean": 0, "median": 0, "max": 0, "std": 0}
    if not df.empty:
        df["amount"] = pd.to_numeric(df["amount"])
        by_type = {str(k): float(v) for k, v in df.groupby("transaction_type")["amount"].sum().items()}
        df["month"] = pd.to_datetime(df["transaction_date"]).dt.to_period("M").astype(str)
        grouped = df.groupby(["month", "transaction_type"])["amount"].sum().unstack(fill_value=0)
        for month, row in grouped.iterrows():
            monthly.append({"month": month, "deposits": float(row.get("Deposit", 0)),
                            "withdrawals": float(row.get("Withdrawal", 0))})
        vals = df["amount"].to_numpy(dtype=float)
        stats = {"mean": float(np.mean(vals)), "median": float(np.median(vals)),
                 "max": float(np.max(vals)), "std": float(np.std(vals))}
    return render_template("analytics.html", title="Analytics", monthly=monthly,
                           by_type=by_type, stats=stats, total=len(df))


@app.route("/review")
def review():
    df = fetch_transactions()
    flags = review_flags(df)
    return render_template("review.html", title="Review queue", flags=flags)


@app.route("/reports")
def reports():
    df = fetch_transactions()
    monthly = []
    if not df.empty:
        df["month"] = pd.to_datetime(df["transaction_date"]).dt.to_period("M").astype(str)
        for month, group in df.groupby("month"):
            monthly.append({"month": month, "transactions": len(group),
                "deposits": float(group.loc[group.transaction_type == "Deposit", "amount"].sum()),
                "withdrawals": float(group.loc[group.transaction_type == "Withdrawal", "amount"].sum())})
    return render_template("reports.html", title="Reports", monthly=monthly)


@app.route("/export/<kind>.csv")
def export_csv(kind):
    df = fetch_transactions()
    if kind == "transactions":
        export_df = df[["transaction_id", "account_id", "display_name", "transaction_date",
                        "transaction_type", "amount", "description"]] if not df.empty else pd.DataFrame(
            columns=["transaction_id", "account_id", "display_name", "transaction_date", "transaction_type", "amount", "description"])
        filename = "finsight_transactions.csv"
    elif kind == "accounts":
        export_df = pd.DataFrame(fetch_accounts())
        filename = "finsight_account_summary.csv"
    elif kind == "monthly":
        if df.empty:
            export_df = pd.DataFrame(columns=["month", "transactions", "deposits", "withdrawals"])
        else:
            df["month"] = pd.to_datetime(df["transaction_date"]).dt.to_period("M").astype(str)
            export_df = df.groupby("month").apply(lambda g: pd.Series({
                "transactions": len(g),
                "deposits": g.loc[g.transaction_type == "Deposit", "amount"].sum(),
                "withdrawals": g.loc[g.transaction_type == "Withdrawal", "amount"].sum()
            })).reset_index()
        filename = "finsight_monthly_report.csv"
    else:
        flash("Unknown report type.", "error")
        return redirect(url_for("reports"))
    output = StringIO()
    export_df.to_csv(output, index=False)
    memory = BytesIO(output.getvalue().encode("utf-8-sig"))
    memory.seek(0)
    return send_file(memory, mimetype="text/csv", as_attachment=True, download_name=filename)


@app.route("/charts/monthly.png")
def monthly_chart():
    df = fetch_transactions()
    fig, ax = plt.subplots(figsize=(8, 3.3), dpi=130)
    if df.empty:
        ax.text(.5, .5, "No transactions yet", ha="center", va="center")
        ax.set_axis_off()
    else:
        df["month"] = pd.to_datetime(df["transaction_date"]).dt.to_period("M").astype(str)
        grouped = df.pivot_table(index="month", columns="transaction_type", values="amount",
                                 aggfunc="sum", fill_value=0).tail(8)
        x = np.arange(len(grouped.index))
        width = .36
        ax.bar(x - width/2, grouped.get("Deposit", pd.Series(0, index=grouped.index)), width, label="Deposits")
        ax.bar(x + width/2, grouped.get("Withdrawal", pd.Series(0, index=grouped.index)), width, label="Withdrawals")
        ax.set_xticks(x, grouped.index, rotation=25, ha="right")
        ax.set_ylabel("Amount (₹)")
        ax.legend(frameon=False, ncols=2)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/reset-demo", methods=["POST"])
def reset_demo():
    with get_db() as db:
        db.execute("DELETE FROM transactions")
        db.execute("DELETE FROM accounts")
        db.execute("DELETE FROM customers")
        db.execute("DELETE FROM sqlite_sequence WHERE name IN ('transactions','accounts','customers')")
    seed_demo_data()
    flash("Demo data has been reset to the original synthetic dataset.", "success")
    return redirect(url_for("dashboard"))


@app.route("/methodology")
def methodology():
    return render_template("methodology.html", title="Methodology")


init_db()
seed_demo_data()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
