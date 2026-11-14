"""Ledger calculations: balances, bill status, summaries."""

from __future__ import annotations

import sqlite3
from typing import Any


def money(value: float | None) -> float:
    return round(float(value or 0), 2)


def customer_totals(db: sqlite3.Connection, customer_id: int) -> dict[str, float]:
    billed = db.execute(
        "SELECT COALESCE(SUM(total), 0) AS t FROM bills WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()["t"]
    paid = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM payments WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()["t"]
    return {
        "billed": money(billed),
        "paid": money(paid),
        "balance": money(billed - paid),
    }


def bill_paid_amount(db: sqlite3.Connection, bill_id: int) -> float:
    row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM payments WHERE bill_id = ?",
        (bill_id,),
    ).fetchone()
    return money(row["t"])


def bill_status(total: float, paid: float) -> str:
    total = money(total)
    paid = money(paid)
    if paid <= 0:
        return "Unpaid"
    if paid + 0.009 >= total:
        return "Paid"
    return "Partial"


def enrich_bill(db: sqlite3.Connection, bill: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(bill)
    paid = bill_paid_amount(db, data["id"])
    data["paid"] = paid
    data["due"] = money(data["total"] - paid)
    data["status"] = bill_status(data["total"], paid)
    return data


def dashboard_stats(db: sqlite3.Connection) -> dict[str, Any]:
    today = db.execute(
        "SELECT COALESCE(SUM(total), 0) AS t FROM bills WHERE bill_date = date('now','localtime')"
    ).fetchone()["t"]
    month = db.execute(
        """
        SELECT COALESCE(SUM(total), 0) AS t FROM bills
        WHERE strftime('%Y-%m', bill_date) = strftime('%Y-%m', 'now', 'localtime')
        """
    ).fetchone()["t"]
    paid_today = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM payments WHERE payment_date = date('now','localtime')"
    ).fetchone()["t"]
    billed = db.execute("SELECT COALESCE(SUM(total), 0) AS t FROM bills").fetchone()["t"]
    paid_all = db.execute("SELECT COALESCE(SUM(amount), 0) AS t FROM payments").fetchone()["t"]
    return {
        "sales_today": money(today),
        "sales_month": money(month),
        "collected_today": money(paid_today),
        "outstanding": money(billed - paid_all),
        "customer_count": db.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"],
        "bill_count": db.execute("SELECT COUNT(*) AS c FROM bills").fetchone()["c"],
    }


def customer_ledger_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    customers = db.execute(
        "SELECT id, name, phone FROM customers ORDER BY name COLLATE NOCASE"
    ).fetchall()
    rows = []
    for c in customers:
        totals = customer_totals(db, c["id"])
        if totals["billed"] == 0 and totals["paid"] == 0:
            continue
        rows.append({**dict(c), **totals})
    rows.sort(key=lambda r: r["balance"], reverse=True)
    return rows
