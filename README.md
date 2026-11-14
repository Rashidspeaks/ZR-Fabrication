# ZR Fabrication — Bill Ledger

Python bill ledger for the ZR Fabrication iron store. Track customers, iron products, bills, payments, and outstanding balances.

## Features

- **Dashboard** — today's sales, month total, collections, outstanding dues
- **Customers** — accounts with billed / paid / balance
- **Products** — angles, channels, pipes, bars, sheets, labour & transport rates
- **Bills** — multi-line invoices (kg / ft / pcs / job), discount, optional payment on save
- **Payments** — cash / bank / JazzCash / EasyPaisa / cheque against a bill or customer
- **Ledger** — receivable summary across all customers
- **Printable bills** — browser print view

Amounts are in **PKR (Rs)**. Data is stored in local SQLite (`data/ledger.db`).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

First launch seeds sample iron products and a few customers so you can create a bill immediately.

## Tests

```bash
pytest -q
```

## Project layout

```
app/
  db.py          SQLite schema & seed data
  ledger.py      Balances and bill status
  routes.py      Web routes
  templates/     UI pages
  static/        Styles
run.py           Dev server
tests/           Pytest suite
data/            SQLite database (created at runtime)
```
