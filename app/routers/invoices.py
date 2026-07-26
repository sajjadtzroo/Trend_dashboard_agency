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
