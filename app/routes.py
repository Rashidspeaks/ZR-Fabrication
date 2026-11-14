"""HTTP routes for the bill ledger."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db, next_bill_no
from app.ledger import (
    customer_ledger_rows,
    customer_totals,
    dashboard_stats,
    enrich_bill,
    money,
)

bp = Blueprint("main", __name__)


def _parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return money(float(value)) if value not in (None, "") else default
    except ValueError:
        return default


@bp.route("/")
def index():
    db = get_db()
    stats = dashboard_stats(db)
    recent_bills = db.execute(
        """
        SELECT b.*, c.name AS customer_name
        FROM bills b JOIN customers c ON c.id = b.customer_id
        ORDER BY b.id DESC LIMIT 8
        """
    ).fetchall()
    bills = [enrich_bill(db, b) for b in recent_bills]
    dues = customer_ledger_rows(db)[:8]
    return render_template("index.html", stats=stats, bills=bills, dues=dues)


# ---- Customers ----


@bp.route("/customers")
def customers():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    if q:
        rows = db.execute(
            """
            SELECT * FROM customers
            WHERE name LIKE ? OR phone LIKE ? OR address LIKE ?
            ORDER BY name COLLATE NOCASE
            """,
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM customers ORDER BY name COLLATE NOCASE"
        ).fetchall()
    customers_list = [{**dict(r), **customer_totals(db, r["id"])} for r in rows]
    return render_template("customers.html", customers=customers_list, q=q)


@bp.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Customer name is required.", "error")
            return render_template("customer_form.html", customer=request.form, title="New customer")
        db = get_db()
        db.execute(
            "INSERT INTO customers (name, phone, address, notes) VALUES (?,?,?,?)",
            (
                name,
                (request.form.get("phone") or "").strip(),
                (request.form.get("address") or "").strip(),
                (request.form.get("notes") or "").strip(),
            ),
        )
        db.commit()
        flash(f"Customer “{name}” saved.", "ok")
        return redirect(url_for("main.customers"))
    return render_template("customer_form.html", customer=None, title="New customer")


@bp.route("/customers/<int:customer_id>")
def customer_detail(customer_id: int):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if customer is None:
        flash("Customer not found.", "error")
        return redirect(url_for("main.customers"))
    totals = customer_totals(db, customer_id)
    bills = [
        enrich_bill(db, b)
        for b in db.execute(
            "SELECT * FROM bills WHERE customer_id = ? ORDER BY bill_date DESC, id DESC",
            (customer_id,),
        ).fetchall()
    ]
    payments = db.execute(
        """
        SELECT p.*, b.bill_no
        FROM payments p
        LEFT JOIN bills b ON b.id = p.bill_id
        WHERE p.customer_id = ?
        ORDER BY p.payment_date DESC, p.id DESC
        """,
        (customer_id,),
    ).fetchall()
    return render_template(
        "customer_detail.html",
        customer=customer,
        totals=totals,
        bills=bills,
        payments=payments,
    )


@bp.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
def customer_edit(customer_id: int):
    db = get_db()
    customer = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if customer is None:
        flash("Customer not found.", "error")
        return redirect(url_for("main.customers"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Customer name is required.", "error")
            return render_template(
                "customer_form.html", customer=request.form, title="Edit customer"
            )
        db.execute(
            "UPDATE customers SET name=?, phone=?, address=?, notes=? WHERE id=?",
            (
                name,
                (request.form.get("phone") or "").strip(),
                (request.form.get("address") or "").strip(),
                (request.form.get("notes") or "").strip(),
                customer_id,
            ),
        )
        db.commit()
        flash("Customer updated.", "ok")
        return redirect(url_for("main.customer_detail", customer_id=customer_id))
    return render_template("customer_form.html", customer=customer, title="Edit customer")


# ---- Products ----


@bp.route("/products")
def products():
    db = get_db()
    show_all = request.args.get("all") == "1"
    if show_all:
        rows = db.execute(
            "SELECT * FROM products ORDER BY category, name COLLATE NOCASE"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM products WHERE active = 1 ORDER BY category, name COLLATE NOCASE"
        ).fetchall()
    return render_template("products.html", products=rows, show_all=show_all)


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Product name is required.", "error")
            return render_template("product_form.html", product=request.form, title="New product")
        db = get_db()
        db.execute(
            """
            INSERT INTO products (name, category, unit, rate, description, active)
            VALUES (?,?,?,?,?,1)
            """,
            (
                name,
                (request.form.get("category") or "Iron").strip() or "Iron",
                (request.form.get("unit") or "kg").strip() or "kg",
                _parse_float(request.form.get("rate")),
                (request.form.get("description") or "").strip(),
            ),
        )
        db.commit()
        flash(f"Product “{name}” saved.", "ok")
        return redirect(url_for("main.products"))
    return render_template("product_form.html", product=None, title="New product")


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id: int):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        flash("Product not found.", "error")
        return redirect(url_for("main.products"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Product name is required.", "error")
            return render_template(
                "product_form.html", product=request.form, title="Edit product"
            )
        active = 1 if request.form.get("active") == "1" else 0
        db.execute(
            """
            UPDATE products
            SET name=?, category=?, unit=?, rate=?, description=?, active=?
            WHERE id=?
            """,
            (
                name,
                (request.form.get("category") or "Iron").strip() or "Iron",
                (request.form.get("unit") or "kg").strip() or "kg",
                _parse_float(request.form.get("rate")),
                (request.form.get("description") or "").strip(),
                active,
                product_id,
            ),
        )
        db.commit()
        flash("Product updated.", "ok")
        return redirect(url_for("main.products"))
    return render_template("product_form.html", product=product, title="Edit product")


# ---- Bills ----


@bp.route("/bills")
def bills():
    db = get_db()
    status_filter = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip()
    rows = db.execute(
        """
        SELECT b.*, c.name AS customer_name
        FROM bills b JOIN customers c ON c.id = b.customer_id
        WHERE (? = '' OR b.bill_no LIKE ? OR c.name LIKE ?)
        ORDER BY b.bill_date DESC, b.id DESC
        """,
        (q, f"%{q}%", f"%{q}%"),
    ).fetchall()
    bills_list = [enrich_bill(db, b) for b in rows]
    if status_filter:
        bills_list = [b for b in bills_list if b["status"] == status_filter]
    return render_template(
        "bills.html", bills=bills_list, q=q, status_filter=status_filter
    )


@bp.route("/bills/new", methods=["GET", "POST"])
def bill_new():
    db = get_db()
    customers = db.execute(
        "SELECT id, name FROM customers ORDER BY name COLLATE NOCASE"
    ).fetchall()
    products = db.execute(
        "SELECT * FROM products WHERE active = 1 ORDER BY category, name COLLATE NOCASE"
    ).fetchall()

    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        bill_date = (request.form.get("bill_date") or date.today().isoformat()).strip()
        notes = (request.form.get("notes") or "").strip()
        discount = _parse_float(request.form.get("discount"))

        descriptions = request.form.getlist("item_description")
        units = request.form.getlist("item_unit")
        quantities = request.form.getlist("item_quantity")
        rates = request.form.getlist("item_rate")
        product_ids = request.form.getlist("item_product_id")

        items = []
        for i, desc in enumerate(descriptions):
            desc = (desc or "").strip()
            if not desc:
                continue
            qty = _parse_float(quantities[i] if i < len(quantities) else None)
            rate = _parse_float(rates[i] if i < len(rates) else None)
            if qty <= 0:
                continue
            unit = (units[i] if i < len(units) else "kg") or "kg"
            pid_raw = product_ids[i] if i < len(product_ids) else ""
            product_id = int(pid_raw) if pid_raw.isdigit() else None
            items.append(
                {
                    "product_id": product_id,
                    "description": desc,
                    "unit": unit,
                    "quantity": qty,
                    "rate": rate,
                    "amount": money(qty * rate),
                }
            )

        if not customer_id or not customer_id.isdigit():
            flash("Select a customer.", "error")
            return render_template(
                "bill_form.html",
                customers=customers,
                products=products,
                bill_no=next_bill_no(),
                today=date.today().isoformat(),
                form=request.form,
            )
        if not items:
            flash("Add at least one bill line.", "error")
            return render_template(
                "bill_form.html",
                customers=customers,
                products=products,
                bill_no=next_bill_no(),
                today=date.today().isoformat(),
                form=request.form,
            )

        subtotal = money(sum(i["amount"] for i in items))
        total = money(max(subtotal - discount, 0))
        bill_no = next_bill_no(db)

        cur = db.execute(
            """
            INSERT INTO bills (bill_no, customer_id, bill_date, notes, subtotal, discount, total)
            VALUES (?,?,?,?,?,?,?)
            """,
            (bill_no, int(customer_id), bill_date, notes, subtotal, discount, total),
        )
        bill_id = cur.lastrowid
        for item in items:
            db.execute(
                """
                INSERT INTO bill_items
                    (bill_id, product_id, description, unit, quantity, rate, amount)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    bill_id,
                    item["product_id"],
                    item["description"],
                    item["unit"],
                    item["quantity"],
                    item["rate"],
                    item["amount"],
                ),
            )

        paid_now = _parse_float(request.form.get("paid_now"))
        if paid_now > 0:
            method = (request.form.get("payment_method") or "Cash").strip() or "Cash"
            db.execute(
                """
                INSERT INTO payments
                    (customer_id, bill_id, amount, payment_date, method, notes)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    int(customer_id),
                    bill_id,
                    money(min(paid_now, total)),
                    bill_date,
                    method,
                    f"Payment on bill {bill_no}",
                ),
            )

        db.commit()
        flash(f"Bill {bill_no} created.", "ok")
        return redirect(url_for("main.bill_detail", bill_id=bill_id))

    return render_template(
        "bill_form.html",
        customers=customers,
        products=products,
        bill_no=next_bill_no(),
        today=date.today().isoformat(),
        form=None,
    )


@bp.route("/bills/<int:bill_id>")
def bill_detail(bill_id: int):
    db = get_db()
    bill = db.execute(
        """
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone,
               c.address AS customer_address
        FROM bills b JOIN customers c ON c.id = b.customer_id
        WHERE b.id = ?
        """,
        (bill_id,),
    ).fetchone()
    if bill is None:
        flash("Bill not found.", "error")
        return redirect(url_for("main.bills"))
    items = db.execute(
        "SELECT * FROM bill_items WHERE bill_id = ? ORDER BY id", (bill_id,)
    ).fetchall()
    payments = db.execute(
        "SELECT * FROM payments WHERE bill_id = ? ORDER BY payment_date, id",
        (bill_id,),
    ).fetchall()
    enriched = enrich_bill(db, bill)
    return render_template(
        "bill_detail.html", bill=enriched, items=items, payments=payments
    )


@bp.route("/bills/<int:bill_id>/delete", methods=["POST"])
def bill_delete(bill_id: int):
    db = get_db()
    bill = db.execute("SELECT bill_no FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if bill is None:
        flash("Bill not found.", "error")
        return redirect(url_for("main.bills"))
    db.execute("DELETE FROM payments WHERE bill_id = ?", (bill_id,))
    db.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    db.commit()
    flash(f"Bill {bill['bill_no']} deleted.", "ok")
    return redirect(url_for("main.bills"))


# ---- Payments ----


@bp.route("/payments", methods=["GET", "POST"])
def payments():
    db = get_db()
    customers = db.execute(
        "SELECT id, name FROM customers ORDER BY name COLLATE NOCASE"
    ).fetchall()

    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        amount = _parse_float(request.form.get("amount"))
        payment_date = (
            request.form.get("payment_date") or date.today().isoformat()
        ).strip()
        method = (request.form.get("method") or "Cash").strip() or "Cash"
        notes = (request.form.get("notes") or "").strip()
        bill_id_raw = request.form.get("bill_id") or ""
        bill_id = int(bill_id_raw) if bill_id_raw.isdigit() else None

        if not customer_id or not customer_id.isdigit() or amount <= 0:
            flash("Customer and a positive amount are required.", "error")
        else:
            if bill_id is not None:
                bill = db.execute(
                    "SELECT id, customer_id FROM bills WHERE id = ?", (bill_id,)
                ).fetchone()
                if bill is None or bill["customer_id"] != int(customer_id):
                    flash("Selected bill does not belong to this customer.", "error")
                    return redirect(url_for("main.payments"))
            db.execute(
                """
                INSERT INTO payments
                    (customer_id, bill_id, amount, payment_date, method, notes)
                VALUES (?,?,?,?,?,?)
                """,
                (int(customer_id), bill_id, amount, payment_date, method, notes),
            )
            db.commit()
            flash("Payment recorded.", "ok")
            return redirect(url_for("main.customer_detail", customer_id=int(customer_id)))

    rows = db.execute(
        """
        SELECT p.*, c.name AS customer_name, b.bill_no
        FROM payments p
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN bills b ON b.id = p.bill_id
        ORDER BY p.payment_date DESC, p.id DESC
        LIMIT 50
        """
    ).fetchall()
    open_bills = db.execute(
        """
        SELECT b.id, b.bill_no, b.customer_id, b.total, c.name AS customer_name
        FROM bills b JOIN customers c ON c.id = b.customer_id
        ORDER BY b.bill_date DESC
        """
    ).fetchall()
    open_bills = [enrich_bill(db, b) for b in open_bills]
    open_bills = [b for b in open_bills if b["due"] > 0]
    return render_template(
        "payments.html",
        payments=rows,
        customers=customers,
        open_bills=open_bills,
        today=date.today().isoformat(),
    )


# ---- Ledger ----


@bp.route("/ledger")
def ledger():
    db = get_db()
    rows = customer_ledger_rows(db)
    total_due = money(sum(r["balance"] for r in rows if r["balance"] > 0))
    total_credit = money(sum(-r["balance"] for r in rows if r["balance"] < 0))
    return render_template(
        "ledger.html",
        rows=rows,
        total_due=total_due,
        total_credit=total_credit,
    )
