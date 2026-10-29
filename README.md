# FinSight | Banking Transaction Analysis System

A responsive Flask web app for a college data analytics project. It maintains synthetic customers, accounts, and transactions, calculates simulated balances, summarizes monthly activity, plots trends, exports CSV reports, and flags unusual records for review.

> **Educational simulation only.** All seeded records are synthetic. Balances are simulated. This is not a real banking platform and does not move money. Do not enter real credentials or sensitive financial information. Review flags are not fraud determinations.

## Features

- Dashboard KPIs and monthly deposits-versus-withdrawals chart
- Synthetic customer and account creation
- Deposit and withdrawal transaction entry with input validation
- Search and filter transaction history
- Account-level summaries and simulated balances
- Monthly analytics using Pandas, descriptive statistics using NumPy, and charts using Matplotlib
- Explainable rule-based review queue
- CSV exports for transaction ledger, account summaries, and monthly reports
- Local SQLite persistence and reset-to-demo-data action
- MySQL schema supplied separately for academic documentation

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract the project folder.
3. Open PowerShell in the extracted folder.
4. Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

5. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

6. Start the website:

```powershell
python app.py
```

7. Open **http://127.0.0.1:5000** in your browser.

The SQLite database `finsight.db` is created automatically in the project folder and seeded with synthetic records on first launch.

## Project structure

```text
FinSight_Banking_Transaction_Analysis/
├── app.py
├── requirements.txt
├── schema_mysql.sql
├── README.md
├── .gitignore
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── transactions.html
│   ├── customers.html
│   ├── accounts.html
│   ├── analytics.html
│   ├── review.html
│   ├── reports.html
│   └── methodology.html
└── static/
    ├── style.css
    └── app.js
```

## Analytics notes

- **Balance:** opening balance + deposits − withdrawals. It is computed from the ledger and is simulated.
- **Monthly grouping:** transactions are grouped by calendar month and transaction type using Pandas.
- **Statistics:** mean, median, maximum, and population standard deviation are computed with NumPy.
- **Chart:** Matplotlib creates a monthly grouped bar chart.
- **Review rule A:** flag any transaction of ₹10,000 or more.
- **Review rule B:** flag records on an account/date where four or more transactions occur.
- A flag is only a review prompt. These simple rules can create false positives and miss unusual activity.

## Database

The app runs with SQLite by default so it is easy to set up for a classroom demo. `schema_mysql.sql` documents the equivalent MySQL entities and constraints for the project report. The MySQL schema is not wired into the default Flask app.

## Limitations and safety

This is a local educational prototype. It has no authentication system, production authorization, CSRF protection, audit logging, or real banking integration. Do not expose it to the public internet or use it with real financial data. For production use, a substantial security and compliance redesign would be required.
