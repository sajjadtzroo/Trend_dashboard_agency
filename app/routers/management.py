"""Management CRUD on dimensions + roll-up metrics. Soft-delete when referenced."""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..cache import invalidate_aggregates, cached
from ..queries import rows
from ..filters import INVOICED, JOINS, Filters, get_filters

router = APIRouter(prefix="/manage", tags=["management"])

# resource -> dim table metadata
RES = {
    "campaigns": {"table": "dim_campaign", "key": "campaign_key", "name": "order_name", "fk": "campaign_key"},
    "projects":  {"table": "dim_project",  "key": "project_key",  "name": "project_name", "fk": "project_key"},
    "users":     {"table": "dim_user",     "key": "user_key",     "name": "account",     "fk": "user_key"},
    "media":     {"table": "dim_media",    "key": "media_key",    "name": "media_name",  "fk": "media_key"},
}

# Per-resource roll-ups. Fact-first (via the shared JOINS) so the standard filter
# bar — client/service/user/date — applies, same as every other endpoint. {where}
# already carries transaction_type='SALE'; we add the invoiced gate + soft-delete flag.
LIST_SQL = {
    "campaigns": """
        SELECT cm.campaign_key AS id, cm.order_name AS name, MAX(pr.project_code) AS project,
               MAX(c.company_name) AS client, COUNT(f.transaction_id) AS rows,
               COALESCE(SUM(f.revenue),0) AS revenue, COALESCE(SUM(f.cost),0) AS cost,
               COALESCE(SUM(f.operational_profit),0) AS profit,
               CASE WHEN SUM(f.revenue)>0 THEN ROUND(SUM(f.operational_profit)/SUM(f.revenue)*100,1) END AS margin
        {JOINS}
        LEFT JOIN dim_campaign cm ON cm.campaign_key = f.campaign_key
        LEFT JOIN dim_project pr ON pr.project_key = cm.project_key
        {where} AND {INVOICED} AND cm.is_active
        GROUP BY cm.campaign_key, cm.order_name ORDER BY revenue DESC""",
    "projects": """
        SELECT pr.project_key AS id, pr.project_code AS name, MAX(pr.project_name) AS title,
               MAX(c.company_name) AS client, COUNT(f.transaction_id) AS rows,
               COALESCE(SUM(f.revenue),0) AS revenue, COALESCE(SUM(f.cost),0) AS cost,
               COALESCE(SUM(f.operational_profit),0) AS profit,
               (SELECT COUNT(*) FROM dim_campaign cm WHERE cm.project_key = pr.project_key) AS campaigns
        {JOINS}
        LEFT JOIN dim_project pr ON pr.project_key = f.project_key
        {where} AND {INVOICED} AND pr.is_active
        GROUP BY pr.project_key, pr.project_code ORDER BY revenue DESC""",
    "users": """
        SELECT u.user_key AS id, u.account AS name, MAX(u.role) AS role,
               COUNT(f.transaction_id) AS rows, COALESCE(SUM(f.revenue),0) AS revenue,
               COALESCE(SUM(f.operational_profit),0) AS profit,
               CASE WHEN SUM(f.revenue)>0 THEN ROUND(SUM(f.operational_profit)/SUM(f.revenue)*100,1) END AS margin
        {JOINS}
        {where} AND {INVOICED} AND u.is_active
        GROUP BY u.user_key, u.account ORDER BY revenue DESC""",
    "media": """
        SELECT m.media_key AS id, m.media_name AS name,
               COUNT(f.transaction_id) AS rows, COALESCE(SUM(f.revenue),0) AS revenue,
               COALESCE(SUM(f.cost),0) AS cost, COALESCE(SUM(f.operational_profit),0) AS profit
        {JOINS} LEFT JOIN dim_media m ON m.media_key = f.media_key
        {where} AND {INVOICED} AND m.is_active
        GROUP BY m.media_key, m.media_name ORDER BY revenue DESC""",
}


def _res(resource):
    if resource not in RES:
        raise HTTPException(404, f"unknown resource '{resource}'")
    return RES[resource]


@router.get("/{resource}")
def list_resource(resource: str, db: Session = Depends(get_db), f: Filters = Depends(get_filters)):
    _res(resource)
    def q():
        where, p = f.where(type_default="SALE")
        sql = LIST_SQL[resource].format(JOINS=JOINS, where=where, INVOICED=INVOICED)
        return rows(db, sql, p)
    return cached(f"manage-{resource}", f.as_params(), q)


@router.get("/{resource}/{item_id}")
def detail(resource: str, item_id: int, db: Session = Depends(get_db)):
    m = _res(resource)

    def q():
        row = rows(db, f"SELECT * FROM {m['table']} WHERE {m['key']} = :id", {"id": item_id})
        if not row:
            raise HTTPException(404, "not found")
        linked = rows(db, f"""
            SELECT f.transaction_type, f.revenue, f.cost, f.operational_profit, f.profit_margin,
                   f.amount, f.balance, f.source_row,
                   d.jalali_year, d.jalali_month, d.jalali_date,
                   c.company_name AS client, sv.service_name AS service,
                   b.brand_name AS brand, os.label AS order_status
            FROM fact_transaction f
            LEFT JOIN dim_date d ON d.date_key = f.date_key
            LEFT JOIN dim_client c ON c.client_key = f.client_key
            LEFT JOIN dim_service sv ON sv.service_key = f.service_key
            LEFT JOIN dim_brand b ON b.brand_key = f.brand_key
            LEFT JOIN dim_order_status os ON os.order_status_key = f.order_status_key
            WHERE f.{m['fk']} = :id ORDER BY d.jalali_year, d.jalali_month, f.transaction_id LIMIT 500
        """, {"id": item_id})
        return {"item": row[0], "transactions": linked}

    return cached(f"manage-{resource}-detail", {"id": item_id}, q)


@router.patch("/{resource}/{item_id}")
def update(resource: str, item_id: int, body: dict = Body(...), db: Session = Depends(get_db)):
    m = _res(resource)
    fields, params = [], {"id": item_id}
    if "name" in body:
        fields.append(f"{m['name']} = :name"); params["name"] = body["name"]
    if resource == "users" and "role" in body:
        fields.append("role = :role"); params["role"] = body["role"]
    if not fields:
        raise HTTPException(400, "nothing to update")
    res = db.execute(text(f"UPDATE {m['table']} SET {', '.join(fields)} WHERE {m['key']} = :id"), params)
    if res.rowcount == 0:
        raise HTTPException(404, "not found")
    db.commit()
    invalidate_aggregates()
    return {"updated": item_id}


@router.delete("/{resource}/{item_id}")
def delete(resource: str, item_id: int, db: Session = Depends(get_db)):
    m = _res(resource)
    refs = db.execute(text(f"SELECT COUNT(*) FROM fact_transaction WHERE {m['fk']} = :id"),
                      {"id": item_id}).scalar_one()
    if refs:  # referenced -> soft-delete only
        db.execute(text(f"UPDATE {m['table']} SET is_active = FALSE WHERE {m['key']} = :id"), {"id": item_id})
        mode = "soft"
    else:
        db.execute(text(f"DELETE FROM {m['table']} WHERE {m['key']} = :id"), {"id": item_id})
        mode = "hard"
    db.commit()
    invalidate_aggregates()
    return {"deleted": item_id, "mode": mode, "references": refs}
