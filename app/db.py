"""SQLite helpers for the bill ledger."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_: Any = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Iron',
    unit TEXT NOT NULL DEFAULT 'kg',
    rate REAL NOT NULL DEFAULT 0,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    bill_date TEXT NOT NULL,
    notes TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    discount REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS bill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    description TEXT NOT NULL,
    unit TEXT NOT NULL,
    quantity REAL NOT NULL,
    rate REAL NOT NULL,
    amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    bill_id INTEGER REFERENCES bills(id) ON DELETE SET NULL,
    amount REAL NOT NULL,
    payment_date TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'Cash',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_bills_customer ON bills(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);
"""


def init_db() -> None:
    from flask import current_app

    current_app.teardown_appcontext(close_db)
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def next_bill_no(db: sqlite3.Connection | None = None) -> str:
    db = db or get_db()
    year = date.today().year
    prefix = f"ZR-{year}-"
    row = db.execute(
        "SELECT bill_no FROM bills WHERE bill_no LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    if row is None:
        return f"{prefix}0001"
    try:
        seq = int(str(row["bill_no"]).split("-")[-1]) + 1
    except ValueError:
        seq = 1
    return f"{prefix}{seq:04d}"


def seed_if_empty() -> None:
    db = get_db()
    count = db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if count:
        return

    products = [
        ("MS Angle 1.5\"", "Angle", "kg", 220.0, "Mild steel angle"),
        ("MS Angle 2\"", "Angle", "kg", 220.0, "Mild steel angle"),
        ("MS Channel 3\"", "Channel", "kg", 230.0, "Mild steel channel"),
        ("MS Channel 4\"", "Channel", "kg", 230.0, "Mild steel channel"),
        ("MS Pipe 1\"", "Pipe", "kg", 250.0, "Round pipe"),
        ("MS Pipe 1.5\"", "Pipe", "kg", 250.0, "Round pipe"),
        ("MS Square Pipe 1\"", "Pipe", "kg", 255.0, "Square hollow section"),
        ("MS Round Bar 12mm", "Bar", "kg", 240.0, "Round bar"),
        ("MS Round Bar 16mm", "Bar", "kg", 240.0, "Round bar"),
        ("MS Flat Bar 1\"", "Flat", "kg", 225.0, "Flat bar"),
        ("MS Sheet 18 gauge", "Sheet", "kg", 260.0, "Sheet metal"),
        ("MS Sheet 16 gauge", "Sheet", "kg", 255.0, "Sheet metal"),
        ("Cutting / Labour", "Service", "job", 500.0, "Fabrication labour"),
        ("Welding Job", "Service", "job", 800.0, "Welding work"),
        ("Transport", "Service", "trip", 1000.0, "Delivery charge"),
    ]
    db.executemany(
        "INSERT INTO products (name, category, unit, rate, description) VALUES (?,?,?,?,?)",
        products,
    )

    customers = [
        ("Ahmed Traders", "0300-1234567", "Lahore", "Regular buyer"),
        ("Khan Iron Works", "0321-7654321", "Sheikhupura", ""),
        ("Cash Customer", "", "", "Walk-in sales"),
    ]
    db.executemany(
        "INSERT INTO customers (name, phone, address, notes) VALUES (?,?,?,?)",
        customers,
    )
    db.commit()
