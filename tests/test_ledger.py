"""Tests for ZR Fabrication bill ledger."""

from __future__ import annotations

import pytest

from app import create_app
from app.db import get_db, next_bill_no
from app.ledger import bill_status, customer_totals, money


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    application = create_app(db_path=str(db_path))
    application.config["TESTING"] = True
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_seed_products_and_customers(app):
    with app.app_context():
        db = get_db()
        products = db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        customers = db.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
        assert products >= 10
        assert customers >= 1


def test_money_and_status():
    assert money(10.456) == 10.46
    assert bill_status(100, 0) == "Unpaid"
    assert bill_status(100, 40) == "Partial"
    assert bill_status(100, 100) == "Paid"
    assert bill_status(100, 100.004) == "Paid"


def test_create_bill_and_balance(client, app):
    with app.app_context():
        db = get_db()
        customer_id = db.execute(
            "SELECT id FROM customers ORDER BY id LIMIT 1"
        ).fetchone()["id"]

    response = client.post(
        "/bills/new",
        data={
            "customer_id": str(customer_id),
            "bill_date": "2026-11-14",
            "notes": "Test load",
            "discount": "50",
            "item_description": ["MS Angle 2\"", ""],
            "item_unit": ["kg", "kg"],
            "item_quantity": ["10", ""],
            "item_rate": ["220", ""],
            "item_product_id": ["", ""],
            "paid_now": "500",
            "payment_method": "Cash",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        db = get_db()
        bill = db.execute("SELECT * FROM bills ORDER BY id DESC LIMIT 1").fetchone()
        assert bill is not None
        assert bill["subtotal"] == 2200.0
        assert bill["discount"] == 50.0
        assert bill["total"] == 2150.0
        assert bill["bill_no"].startswith("ZR-")

        totals = customer_totals(db, customer_id)
        assert totals["billed"] == 2150.0
        assert totals["paid"] == 500.0
        assert totals["balance"] == 1650.0


def test_dashboard_and_ledger_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/customers").status_code == 200
    assert client.get("/products").status_code == 200
    assert client.get("/bills").status_code == 200
    assert client.get("/payments").status_code == 200
    assert client.get("/ledger").status_code == 200


def test_add_customer_and_product(client, app):
    r = client.post(
        "/customers/new",
        data={
            "name": "City Steel Mart",
            "phone": "03001112223",
            "address": "Faisalabad",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"City Steel Mart" in r.data

    r = client.post(
        "/products/new",
        data={
            "name": "MS Tee 2\"",
            "category": "Angle",
            "unit": "kg",
            "rate": "235",
            "description": "Tee section",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert b"MS Tee" in r.data


def test_general_payment(client, app):
    with app.app_context():
        db = get_db()
        customer_id = db.execute(
            "INSERT INTO customers (name) VALUES ('Pay Test')"
        ).lastrowid
        bill_no = next_bill_no(db)
        db.execute(
            """
            INSERT INTO bills (bill_no, customer_id, bill_date, subtotal, discount, total)
            VALUES (?, ?, '2026-11-01', 1000, 0, 1000)
            """,
            (bill_no, customer_id),
        )
        db.commit()

    r = client.post(
        "/payments",
        data={
            "customer_id": str(customer_id),
            "bill_id": "",
            "amount": "300",
            "payment_date": "2026-11-14",
            "method": "Bank",
            "notes": "Advance",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        totals = customer_totals(get_db(), customer_id)
        assert totals["balance"] == 700.0
