"""Aggregate dashboard endpoints — all Jalali-aware, all Redis-cached."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..cache import cached
from ..filters import Filters, get_filters, JOINS, ORDERS, ORDER_ID
from ..queries import rows

router = APIRouter(tags=["dashboard"])

# Business rule: headline revenue/cost = REALIZED sales only — SALE lines that
# reached the 'Invoice' funnel stage (matches the source sheet's grand total).
# Pipeline stages (Opportunity/Confirm/Proposal/…) show in the funnel/breakdown
# views, which sum f.revenue directly. AR/AP-derived figures stay zero until an
# invoice/supplier ledger is loaded (not present in the funnel CSV).
_INVOICE = "(SELECT order_status_key FROM dim_order_status WHERE label='Invoice')"
REV  = f"COALESCE(SUM(f.revenue) FILTER (WHERE f.transaction_type='SALE' AND f.order_status_key={_INVOICE}),0)"
COST = f"COALESCE(SUM(f.cost)    FILTER (WHERE f.transaction_type='SALE' AND f.order_status_key={_INVOICE}),0)"


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    """Distinct filter options for the UI (clients, services, users, Jalali months present)."""
    def q():
        return {
            "clients": [r["v"] for r in rows(db, "SELECT DISTINCT company_name AS v FROM dim_client ORDER BY 1", {})],
            "services": [r["v"] for r in rows(db, "SELECT service_name AS v FROM dim_service ORDER BY 1", {})],
            "users": [r["v"] for r in rows(db, "SELECT account AS v FROM dim_user WHERE is_active ORDER BY 1", {})],
            "months": rows(db, """SELECT DISTINCT d.jalali_year, d.jalali_month,
                                   (d.jalali_year*100+d.jalali_month) AS yyyymm, d.jalali_month_name_fa
                                   FROM fact_transaction f JOIN dim_date d ON d.date_key=f.date_key
                                   ORDER BY yyyymm""", {}),
        }
    return cached("meta", {}, q)


@router.get("/kpis")
def kpis(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where()
        sql = f"""
        SELECT
          {REV}          AS revenue,
          {COST}         AS cost,
          {REV} - {COST} AS op_profit,
          CASE WHEN {REV} > 0 THEN ROUND(({REV} - {COST}) / {REV} * 100, 1) END AS avg_margin,
          COALESCE(SUM(balance) FILTER (WHERE f.transaction_type='RECEIVABLE'),0)            AS ar_outstanding,
          COALESCE(SUM(balance) FILTER (WHERE f.transaction_type='PAYABLE'),0)               AS ap_outstanding
        {JOINS}{where}"""
        cur = rows(db, sql, p)[0]

        # Comparison context: same window one Jalali year earlier (YYYYMM − 100),
        # only when a date range is set — otherwise there's no meaningful prior.
        if f.date_from or f.date_to:
            pf = Filters(**{**f.as_params(),
                            "date_from": (f.date_from - 100) if f.date_from else None,
                            "date_to": (f.date_to - 100) if f.date_to else None})
            pw, pp = pf.where()
            pr = rows(db, f"SELECT {REV} AS revenue, {COST} AS cost, {REV}-{COST} AS op_profit {JOINS}{pw}", pp)[0]

            def delta(c, prev):
                c, prev = float(c or 0), float(prev or 0)
                return round((c - prev) / prev * 100, 1) if prev else None

            cur["delta"] = {"revenue": delta(cur["revenue"], pr["revenue"]),
                            "cost": delta(cur["cost"], pr["cost"]),
                            "op_profit": delta(cur["op_profit"], pr["op_profit"])}
        else:
            cur["delta"] = None
        return cur
    return cached("kpis", f.as_params(), q)


@router.get("/funnel")
def funnel(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(type_default="SALE")
        sql = f"""
        SELECT os.label AS order_status, os.funnel_rank,
               {ORDERS} AS count, COALESCE(SUM(f.revenue),0) AS revenue
        {JOINS} LEFT JOIN dim_order_status os ON os.order_status_key = f.order_status_key
        {where} GROUP BY os.label, os.funnel_rank ORDER BY os.funnel_rank"""
        return rows(db, sql, p)
    return cached("funnel", f.as_params(), q)


# Per-stage breakdown for the Sales Funnel section: every status x dimension value.
FUNNEL_BY = {"account": "u.account", "client": "c.company_name", "service": "sv.service_name"}


@router.get("/funnel-breakdown")
def funnel_breakdown(by: str = "account", db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    grp = FUNNEL_BY.get(by, FUNNEL_BY["account"])
    def q():
        where, p = f.where(type_default="SALE")
        sql = f"""
        SELECT os.label AS order_status, os.funnel_rank, {grp} AS dim,
               {ORDERS} AS count, COALESCE(SUM(f.revenue),0) AS revenue
        {JOINS} LEFT JOIN dim_order_status os ON os.order_status_key = f.order_status_key
        {where} AND {grp} IS NOT NULL
        GROUP BY os.label, os.funnel_rank, {grp}
        ORDER BY os.funnel_rank, revenue DESC"""
        return rows(db, sql, p)
    return cached("funnel-breakdown", {**f.as_params(), "by": by}, q)


@router.get("/revenue-by-service")
def revenue_by_service(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(type_default="SALE")
        sql = f"""
        SELECT sv.service_name AS service,
               COALESCE(SUM(f.revenue),0) AS revenue,
               COALESCE(SUM(f.cost),0) AS cost,
               COALESCE(SUM(f.operational_profit),0) AS profit
        {JOINS} {where} AND f.order_status_key = {_INVOICE}
        GROUP BY sv.service_name ORDER BY revenue DESC"""
        return rows(db, sql, p)
    return cached("revenue-by-service", f.as_params(), q)


@router.get("/revenue-trend")
def revenue_trend(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where()
        sql = f"""
        SELECT d.jalali_year, d.jalali_month, d.jalali_month_name_fa,
               {REV} AS revenue, {COST} AS cost
        {JOINS} {where}
        GROUP BY d.jalali_year, d.jalali_month, d.jalali_month_name_fa
        ORDER BY d.jalali_year, d.jalali_month"""
        return rows(db, sql, p)
    return cached("revenue-trend", f.as_params(), q)


@router.get("/top-clients")
def top_clients(limit: int = 10, db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(); p["limit"] = limit
        sql = f"""
        SELECT c.company_name AS client,
               {REV} AS revenue,
               {REV} - {COST} AS profit,
               CASE WHEN {REV} > 0 THEN ROUND(({REV} - {COST}) / {REV} * 100, 1) END AS margin
        {JOINS} {where} GROUP BY c.company_name ORDER BY revenue DESC LIMIT :limit"""
        return rows(db, sql, p)
    return cached("top-clients", {**f.as_params(), "limit": limit}, q)


@router.get("/top-campaigns")
def top_campaigns(limit: int = 10, db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(type_default="SALE"); p["limit"] = limit
        sql = f"""
        SELECT cm.order_name AS campaign,
               COALESCE(SUM(f.revenue),0) AS revenue,
               COALESCE(SUM(f.operational_profit),0) AS profit,
               CASE WHEN SUM(f.revenue)>0 THEN ROUND(SUM(f.operational_profit)/SUM(f.revenue)*100,1) END AS margin
        {JOINS} LEFT JOIN dim_campaign cm ON cm.campaign_key = f.campaign_key
        {where} AND f.order_status_key = {_INVOICE}
        GROUP BY cm.order_name ORDER BY revenue DESC LIMIT :limit"""
        return rows(db, sql, p)
    return cached("top-campaigns", {**f.as_params(), "limit": limit}, q)


@router.get("/brands")
def brands(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    """Per-brand roll-up for the Brands compare page."""
    def q():
        where, p = f.where(type_default="SALE")
        sql = f"""
        SELECT b.brand_name AS brand, MAX(c.company_name) AS client,
               COALESCE(SUM(f.revenue),0) AS revenue, COALESCE(SUM(f.cost),0) AS cost,
               COALESCE(SUM(f.operational_profit),0) AS profit,
               {ORDERS} AS orders,
               CASE WHEN SUM(f.revenue)>0 THEN ROUND(SUM(f.operational_profit)/SUM(f.revenue)*100,1) END AS margin
        {JOINS} {where} AND f.order_status_key = {_INVOICE} AND b.brand_name IS NOT NULL
        GROUP BY b.brand_name ORDER BY revenue DESC"""
        return rows(db, sql, p)
    return cached("brands", f.as_params(), q)


@router.get("/receivables")
def receivables(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(type_default="RECEIVABLE")
        sql = f"""
        SELECT c.company_name AS client,
               COALESCE(SUM(f.final_amount),0) AS final_amount,
               COALESCE(SUM(f.receivable),0) AS receivable,
               COALESCE(SUM(f.amount_paid),0) AS paid,
               COALESCE(SUM(f.balance),0) AS balance,
               COUNT(*) AS invoices
        {JOINS} {where} GROUP BY c.company_name HAVING SUM(f.balance) <> 0 ORDER BY balance DESC"""
        return rows(db, sql, p)
    return cached("receivables", f.as_params(), q)


@router.get("/payables")
def payables(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    def q():
        where, p = f.where(type_default="PAYABLE")
        sql = f"""
        SELECT s.supplier_name AS supplier,
               COALESCE(SUM(f.amount),0) AS total,
               COALESCE(SUM(f.amount_paid),0) AS paid,
               COALESCE(SUM(f.balance),0) AS balance,
               COUNT(*) AS bills
        {JOINS} LEFT JOIN dim_supplier s ON s.supplier_key = f.supplier_key
        {where} GROUP BY s.supplier_name HAVING SUM(f.balance) <> 0 ORDER BY balance DESC"""
        return rows(db, sql, p)
    return cached("payables", f.as_params(), q)


def _aging(db, f: Filters, ttype: str):
    """Outstanding balance bucketed by invoice age (0-30/31-60/61-90/90+ days).
    ponytail: 'now' = the newest gregorian_date in the filtered set (the data has no
    live clock). Calibration knob — swap `(SELECT d0 FROM ref)` for CURRENT_DATE if the
    dataset is kept current. type_default always sets a WHERE clause, so `AND` is safe."""
    where, p = f.where(type_default=ttype)
    sql = f"""
    WITH scoped AS (
      SELECT f.balance, d.gregorian_date {JOINS} {where} AND f.balance <> 0
    ), ref AS (SELECT MAX(gregorian_date) AS d0 FROM scoped)
    SELECT bucket, COALESCE(SUM(balance),0) AS balance, COUNT(*) AS count FROM (
      SELECT balance, CASE
        WHEN (SELECT d0 FROM ref) - gregorian_date <= 30 THEN '0-30'
        WHEN (SELECT d0 FROM ref) - gregorian_date <= 60 THEN '31-60'
        WHEN (SELECT d0 FROM ref) - gregorian_date <= 90 THEN '61-90'
        ELSE '90+' END AS bucket
      FROM scoped
    ) t GROUP BY bucket ORDER BY bucket"""
    return rows(db, sql, p)


@router.get("/receivables-aging")
def receivables_aging(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    return cached("receivables-aging", f.as_params(), lambda: _aging(db, f, "RECEIVABLE"))


@router.get("/payables-aging")
def payables_aging(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    return cached("payables-aging", f.as_params(), lambda: _aging(db, f, "PAYABLE"))


@router.get("/fulfillment-trend")
def fulfillment_trend(db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    """Monthly average delivery/fulfillment % for SALE lines (0..100)."""
    def q():
        where, p = f.where(type_default="SALE")
        sql = f"""
        SELECT jalali_year, jalali_month, jalali_month_name_fa,
               ROUND(AVG(pct), 1) AS fulfillment
        FROM (SELECT DISTINCT d.jalali_year, d.jalali_month, d.jalali_month_name_fa,
                     {ORDER_ID} AS order_id, f.fulfillment_pct AS pct   -- once per order, not per channel
              {JOINS} {where} AND f.fulfillment_pct IS NOT NULL) t
        GROUP BY jalali_year, jalali_month, jalali_month_name_fa
        ORDER BY jalali_year, jalali_month"""
        return rows(db, sql, p)
    return cached("fulfillment-trend", f.as_params(), q)
