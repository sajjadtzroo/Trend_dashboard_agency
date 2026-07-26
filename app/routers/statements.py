"""FP&A financial statements — IFRS/IAS aligned, derived from fact_transaction."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..cache import cached
from ..filters import Filters, get_filters, JOINS
from ..queries import rows

router = APIRouter(prefix="/statements", tags=["statements"])


def _scalars(db: Session, f: Filters) -> dict:
    where, p = f.where()
    sql = f"""
    SELECT
      COALESCE(SUM(revenue)            FILTER (WHERE f.transaction_type='SALE'),0)       AS revenue,
      COALESCE(SUM(cost)               FILTER (WHERE f.transaction_type='SALE'),0)       AS cost,
      COALESCE(SUM(operational_profit) FILTER (WHERE f.transaction_type='SALE'),0)       AS operating_profit,
      COALESCE(SUM(vat_amount)         FILTER (WHERE f.transaction_type='RECEIVABLE'),0) AS vat,
      COALESCE(SUM(balance)            FILTER (WHERE f.transaction_type='RECEIVABLE'),0) AS receivables,
      COALESCE(SUM(insurance_amount)   FILTER (WHERE f.transaction_type='RECEIVABLE'),0) AS insurance_retention,
      COALESCE(SUM(balance)            FILTER (WHERE f.transaction_type='PAYABLE'),0)    AS payables
    {JOINS}{where}"""
    s = rows(db, sql, p)[0]
    s["gross_profit"] = s["revenue"] - s["cost"]
    s["operating_expenses"] = s["gross_profit"] - s["operating_profit"]
    s["net_profit"] = s["operating_profit"] - s["vat"]
    return {k: float(v) for k, v in s.items()}


def _prior(f: Filters) -> Filters:
    """Prior comparative period = same window shifted back one Jalali year (IAS 1)."""
    if not (f.date_from and f.date_to):
        return None
    return Filters(f.date_from - 100, f.date_to - 100, f.client, f.brand, f.service, f.user, f.transaction_type)


def _line(label, cur, prior, standard=None, indent=False):
    p = prior if prior is not None else None
    change = round((cur - p) / p * 100, 1) if p else None
    return {"label": label, "current": cur, "prior": p, "change_pct": change,
            "standard": standard, "indent": indent}


@router.get("/income")
def income(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        c = _scalars(db, f)
        pf = _prior(f)
        p = _scalars(db, pf) if pf else {}
        g = lambda k: p.get(k)
        return {"title": "Statement of Profit or Loss", "standard": "IAS 1", "currency": "IRR",
                "lines": [
                    _line("Revenue", c["revenue"], g("revenue")),
                    _line("Cost of Sales", -c["cost"], -g("cost") if g("cost") is not None else None, indent=True),
                    _line("Gross Profit", c["gross_profit"], g("gross_profit")),
                    _line("Operating Expenses", -c["operating_expenses"],
                          -g("operating_expenses") if g("operating_expenses") is not None else None, indent=True),
                    _line("Operating Profit", c["operating_profit"], g("operating_profit")),
                    _line("VAT / Tax", -c["vat"], -g("vat") if g("vat") is not None else None, "IAS 12", indent=True),
                    _line("Net Profit", c["net_profit"], g("net_profit")),
                ]}
    return cached("stmt-income", f.as_params(), q)


@router.get("/balance")
def balance(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        c = _scalars(db, f)
        assets = c["receivables"] + c["insurance_retention"]
        liab = c["payables"] + c["vat"]
        # CFA L1 — accounting equation A = L + E, with Equity built from its components
        # (Contributed Capital + Retained Earnings), not plugged. Retained Earnings
        # ARTICULATES with the income statement: it is the cumulative Net Profit.
        total_equity = assets - liab
        retained = c["net_profit"]                    # links to /income Net Profit
        contributed = total_equity - retained         # implied opening/contributed equity (no cash ledger)
        le = liab + total_equity                       # must equal Total Assets
        return {"title": "Statement of Financial Position", "standard": "IAS 1", "currency": "IRR",
                "assets": [
                    _line("Trade Receivables", c["receivables"], None, indent=True),
                    _line("Insurance Retention", c["insurance_retention"], None, "IFRS 15", indent=True),
                    _line("Total Assets", assets, None),
                ],
                "liabilities": [
                    _line("Trade Payables", c["payables"], None, indent=True),
                    _line("VAT Payable", c["vat"], None, "IAS 12", indent=True),
                    _line("Total Liabilities", liab, None),
                ],
                # equity decomposed (CFA): Retained Earnings (from P&L) + contributed/other
                "equity_lines": [
                    _line("Retained Earnings", retained, None, "IAS 1 · from P&L", indent=True),
                    _line("Contributed Capital & Reserves (implied)", contributed, None, None, indent=True),
                    _line("Total Equity", total_equity, None),
                ],
                "equity": _line("Total Equity", total_equity, None),  # back-compat + chart
                # explicit accounting-equation check: A = L + E
                "check": _line("Total Liabilities + Equity", le, None),
                "balances": abs(le - assets) < 1}
    return cached("stmt-balance", f.as_params(), q)


@router.get("/cashflow")
def cashflow(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        c = _scalars(db, f)
        net_cash = c["net_profit"] - c["receivables"] + c["payables"]
        return {"title": "Statement of Cash Flows", "standard": "IAS 7 (indirect)", "currency": "IRR",
                "lines": [
                    _line("Net Profit", c["net_profit"], None),
                    _line("− Δ Trade Receivables", -c["receivables"], None, indent=True),
                    _line("+ Δ Trade Payables", c["payables"], None, indent=True),
                    _line("Net Cash from Operating Activities", net_cash, None),
                ]}
    return cached("stmt-cashflow", f.as_params(), q)


# Operating segments (IFRS 8) — by -> (extra_join, group_expr, label_expr).
# Revenue (SALE) is tagged per campaign/order + brand, not per project (projects
# only carry receivables), so campaign is the revenue-bearing engagement unit here.
SEG = {
    "campaign": ("LEFT JOIN dim_campaign cm ON cm.campaign_key=f.campaign_key", "cm.order_name", "NULL"),
    "brand":    ("", "b.brand_name",    "MAX(c.company_name)"),
    "client":   ("", "c.company_name",  "NULL"),
    "service":  ("", "sv.service_name", "NULL"),
}


@router.get("/segments")
def segments(by: str = "campaign", db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    if by not in SEG:
        by = "campaign"
    join, grp, label = SEG[by]

    def q():
        where, p = f.where(type_default="SALE")
        data = rows(db, f"""
            SELECT {grp} AS segment, {label} AS label,
                   COALESCE(SUM(f.revenue),0) AS revenue, COALESCE(SUM(f.cost),0) AS cost,
                   COALESCE(SUM(f.revenue)-SUM(f.cost),0) AS gross_profit,
                   COALESCE(SUM(f.operational_profit),0) AS operating_profit,
                   COUNT(f.transaction_id) AS orders,
                   CASE WHEN SUM(f.revenue)>0
                        THEN ROUND(SUM(f.operational_profit)/SUM(f.revenue)*100,1) END AS margin
            {JOINS}{join}{where}
            GROUP BY {grp}
            HAVING {grp} IS NOT NULL AND (SUM(f.revenue)<>0 OR SUM(f.cost)<>0)
            ORDER BY revenue DESC""", p)
        return {"by": by, "standard": "IFRS 8", "currency": "IRR", "rows": data}
    return cached("stmt-seg", {**f.as_params(), "by": by}, q)


@router.get("/notes")
def notes(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(type_default="SALE")
        by_service = rows(db, f"""
            SELECT sv.service_name AS service, COALESCE(SUM(f.revenue),0) AS revenue
            {JOINS} {where} GROUP BY sv.service_name ORDER BY revenue DESC""", p)
        return {"revenue_by_service": {"standard": "IFRS 15", "rows": by_service},
                "note": "Ageing of receivables/payables (IFRS 7) available on the Receivables/Payables pages."}
    return cached("stmt-notes", f.as_params(), q)
