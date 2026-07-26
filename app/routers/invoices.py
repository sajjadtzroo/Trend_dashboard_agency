"""Individual invoice endpoints — one row per RECEIVABLE fact (Invoices-sheet line).

Complements /receivables (which only aggregates by client): a filter-aware grid of
every invoice, plus a by-id detail returning every field on the invoice.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..cache import cached, invalidate_aggregates
from ..filters import Filters, get_filters, JOINS
from ..queries import rows

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _pay_status(receivable: float, paid: float) -> int:
    """0 Unpaid / 1 Paid / 2 Partial — matches dim_payment_status seed."""
    if paid <= 0:
        return 0
    if paid >= (receivable or 0):
        return 1
    return 2


def _receivable(db: Session, invoice_id: int) -> dict:
    """The fact row for a RECEIVABLE invoice, or 404. Returns receivable/amount_paid/balance."""
    r = rows(db, """SELECT receivable, amount_paid, balance FROM fact_transaction
                    WHERE transaction_id = :id AND transaction_type = 'RECEIVABLE'""",
             {"id": invoice_id})
    if not r:
        raise HTTPException(404, "invoice not found")
    return r[0]


@router.get("")
def list_invoices(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    """One row per invoice, filter-aware. `id` is the fact row (transaction_id)."""
    def q():
        where, p = f.where(type_default="RECEIVABLE")
        sql = f"""
        SELECT f.transaction_id AS id,
               inv.invoice_number, inv.po_number,
               c.company_name AS client, b.brand_name AS brand,
               pr.project_code AS project, d.jalali_date,
               f.amount, f.final_amount, f.receivable, f.amount_paid, f.balance,
               ps.label AS status
        {JOINS}
        LEFT JOIN dim_invoice inv ON inv.invoice_key = f.invoice_key
        LEFT JOIN dim_project pr  ON pr.project_key  = f.project_key
        LEFT JOIN dim_payment_status ps ON ps.payment_status_key = f.payment_status_key
        {where}
        ORDER BY d.jalali_date DESC NULLS LAST, f.transaction_id DESC"""
        return rows(db, sql, p)
    return cached("invoices", f.as_params(), q)


@router.get("/{invoice_id}")
def invoice_detail(invoice_id: int, db: Session = Depends(get_db)):
    """Every field of a single invoice, by fact row id."""
    sql = """
    SELECT f.transaction_id AS id, f.source_row,
           inv.invoice_number, inv.po_number, inv.clearance_certificate,
           c.company_name AS client, c.national_code, c.category,
           b.brand_name AS brand,
           pr.project_code, pr.project_name,
           u.account,
           d.jalali_date, d.jalali_month_name_fa, d.gregorian_date,
           f.amount, f.vat_rate, f.vat_amount, f.final_amount,
           f.insurance_rate, f.insurance_amount, f.receivable,
           f.amount_paid, f.balance, ps.label AS status
    FROM fact_transaction f
    LEFT JOIN dim_invoice inv ON inv.invoice_key = f.invoice_key
    LEFT JOIN dim_client c    ON c.client_key    = f.client_key
    LEFT JOIN dim_brand b     ON b.brand_key     = f.brand_key
    LEFT JOIN dim_project pr  ON pr.project_key  = f.project_key
    LEFT JOIN dim_user u      ON u.user_key      = f.user_key
    LEFT JOIN dim_date d      ON d.date_key      = f.date_key
    LEFT JOIN dim_payment_status ps ON ps.payment_status_key = f.payment_status_key
    WHERE f.transaction_id = :id AND f.transaction_type = 'RECEIVABLE'"""

    def q():
        row = rows(db, sql, {"id": invoice_id})
        if not row:
            raise HTTPException(404, "invoice not found")
        return row[0]
    return cached("invoice-detail", {"id": invoice_id}, q)


@router.get("/{invoice_id}/payments")
def list_payments(invoice_id: int, db: Session = Depends(get_db)):
    """Ledger for one invoice: opening (imported) balance + each recorded payment
    with a running balance, plus live totals. Not cached — it must reflect writes."""
    inv = _receivable(db, invoice_id)
    receivable = float(inv["receivable"] or 0)
    paid = float(inv["amount_paid"] or 0)
    items = rows(db, """SELECT payment_id, amount, paid_on, method, note, created_at
                        FROM payment WHERE transaction_id = :id
                        ORDER BY paid_on, payment_id""", {"id": invoice_id})
    recorded = sum(float(p["amount"]) for p in items)
    opening = paid - recorded          # the imported portion (see schema note)
    running = opening
    ledger = [{"payment_id": None, "label": "Opening (imported)", "amount": opening,
               "paid_on": None, "method": None, "note": None, "balance": receivable - running}]
    for p in items:
        running += float(p["amount"])
        ledger.append({**p, "label": None, "balance": receivable - running})
    return {"receivable": receivable, "opening": opening, "recorded": recorded,
            "total_paid": paid, "balance": float(inv["balance"] or 0), "rows": ledger}


@router.post("/{invoice_id}/payments")
def add_payment(invoice_id: int, body: dict = Body(...), db: Session = Depends(get_db)):
    """Record a payment: insert the itemized row and bump the fact's paid/balance/status."""
    inv = _receivable(db, invoice_id)
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(400, "amount must be a number")
    balance = float(inv["balance"] or 0)
    if amount <= 0:
        raise HTTPException(400, "amount must be positive")
    if amount > balance + 0.01:                       # tolerate float dust
        raise HTTPException(400, f"amount exceeds outstanding balance ({balance:.0f})")

    new_paid = float(inv["amount_paid"] or 0) + amount
    new_balance = float(inv["receivable"] or 0) - new_paid
    db.execute(text("""INSERT INTO payment (transaction_id, amount, paid_on, method, note)
                       VALUES (:id, :amount, :paid_on, :method, :note)"""),
               {"id": invoice_id, "amount": amount,
                "paid_on": body.get("paid_on") or date.today().isoformat(),
                "method": body.get("method"), "note": body.get("note")})
    db.execute(text("""UPDATE fact_transaction
                       SET amount_paid = :paid, balance = :bal, payment_status_key = :st
                       WHERE transaction_id = :id"""),
               {"paid": new_paid, "bal": new_balance,
                "st": _pay_status(float(inv["receivable"] or 0), new_paid), "id": invoice_id})
    db.commit()
    invalidate_aggregates()
    return {"invoice_id": invoice_id, "total_paid": new_paid, "balance": new_balance}


@router.delete("/{invoice_id}/payments/{payment_id}")
def delete_payment(invoice_id: int, payment_id: int, db: Session = Depends(get_db)):
    """Undo a recorded payment: remove the row and reverse the fact bump."""
    inv = _receivable(db, invoice_id)
    row = rows(db, "SELECT amount FROM payment WHERE payment_id = :pid AND transaction_id = :id",
               {"pid": payment_id, "id": invoice_id})
    if not row:
        raise HTTPException(404, "payment not found")
    amount = float(row[0]["amount"])
    new_paid = float(inv["amount_paid"] or 0) - amount
    new_balance = float(inv["receivable"] or 0) - new_paid
    db.execute(text("DELETE FROM payment WHERE payment_id = :pid"), {"pid": payment_id})
    db.execute(text("""UPDATE fact_transaction
                       SET amount_paid = :paid, balance = :bal, payment_status_key = :st
                       WHERE transaction_id = :id"""),
               {"paid": new_paid, "bal": new_balance,
                "st": _pay_status(float(inv["receivable"] or 0), new_paid), "id": invoice_id})
    db.commit()
    invalidate_aggregates()
    return {"deleted": payment_id, "total_paid": new_paid, "balance": new_balance}


@router.get("/{invoice_id}/related")
def related_invoices(invoice_id: int, db: Session = Depends(get_db)):
    """Other RECEIVABLE invoices for the same client; flag shared brand/project."""
    def q():
        me = rows(db, """SELECT client_key, brand_key, project_key FROM fact_transaction
                         WHERE transaction_id = :id AND transaction_type = 'RECEIVABLE'""",
                  {"id": invoice_id})
        if not me:
            raise HTTPException(404, "invoice not found")
        m = me[0]
        if m["client_key"] is None:
            return []
        return rows(db, """
            SELECT f.transaction_id AS id, inv.invoice_number, b.brand_name AS brand,
                   pr.project_code AS project, d.jalali_date,
                   f.final_amount, f.balance, ps.label AS status,
                   (f.brand_key   IS NOT DISTINCT FROM :brand)   AS same_brand,
                   (f.project_key IS NOT DISTINCT FROM :project) AS same_project
            FROM fact_transaction f
            LEFT JOIN dim_invoice inv ON inv.invoice_key = f.invoice_key
            LEFT JOIN dim_brand b     ON b.brand_key     = f.brand_key
            LEFT JOIN dim_project pr  ON pr.project_key  = f.project_key
            LEFT JOIN dim_date d      ON d.date_key      = f.date_key
            LEFT JOIN dim_payment_status ps ON ps.payment_status_key = f.payment_status_key
            WHERE f.transaction_type = 'RECEIVABLE' AND f.client_key = :client
              AND f.transaction_id <> :id
            ORDER BY same_project DESC, same_brand DESC, d.jalali_date DESC NULLS LAST
            LIMIT 10""",
            {"client": m["client_key"], "brand": m["brand_key"],
             "project": m["project_key"], "id": invoice_id})
    return cached("invoice-related", {"id": invoice_id}, q)


if __name__ == "__main__":  # self-check: payment status transitions (no DB needed)
    assert _pay_status(1000, 0) == 0, "nothing paid -> Unpaid"
    assert _pay_status(1000, 400) == 2, "some paid -> Partial"
    assert _pay_status(1000, 1000) == 1, "fully paid -> Paid"
    assert _pay_status(1000, 1000.001) == 1, "overpaid rounds to Paid"
    assert _pay_status(0, 0) == 0, "zero receivable, nothing paid -> Unpaid"
    print("invoices._pay_status self-check passed")
