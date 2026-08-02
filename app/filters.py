"""Shared query filters. All endpoints accept the same Jalali-aware filter set.

Queries must expose these aliases: f=fact_transaction, d=dim_date, c=dim_client,
sv=dim_service, u=dim_user, b=dim_brand.
"""
from fastapi import Query


class Filters:
    def __init__(self, date_from=None, date_to=None, client=None, brand=None,
                 service=None, user=None, transaction_type=None):
        self.date_from = date_from        # Jalali YYYYMM, e.g. 140401
        self.date_to = date_to
        self.client = client
        self.brand = brand
        self.service = service
        self.user = user
        self.transaction_type = transaction_type

    def where(self, type_default=None):
        """Return (sql_fragment, params). type_default forces a transaction_type when unset."""
        clauses, p = [], {}
        if self.date_from:
            clauses.append("(d.jalali_year*100 + d.jalali_month) >= :date_from")
            p["date_from"] = self.date_from
        if self.date_to:
            clauses.append("(d.jalali_year*100 + d.jalali_month) <= :date_to")
            p["date_to"] = self.date_to
        if self.client:
            clauses.append("c.company_name = :client"); p["client"] = self.client
        if self.brand:
            clauses.append("b.brand_name = :brand"); p["brand"] = self.brand
        if self.service:
            clauses.append("sv.service_name = :service"); p["service"] = self.service
        if self.user:
            clauses.append("u.account = :user"); p["user"] = self.user
        ttype = self.transaction_type or type_default
        if ttype:
            clauses.append("f.transaction_type = :ttype"); p["ttype"] = ttype
        sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return sql, p

    def as_params(self):
        return {"date_from": self.date_from, "date_to": self.date_to, "client": self.client,
                "brand": self.brand, "service": self.service, "user": self.user,
                "transaction_type": self.transaction_type}


def get_filters(
    date_from: int | None = Query(None, description="Jalali YYYYMM inclusive, e.g. 140401"),
    date_to: int | None = Query(None, description="Jalali YYYYMM inclusive"),
    client: str | None = None, brand: str | None = None, service: str | None = None,
    user: str | None = None, transaction_type: str | None = None,
) -> Filters:
    return Filters(date_from, date_to, client, brand, service, user, transaction_type)


# Recognized-revenue gate: only SALE lines that reached the 'Invoice' funnel stage
# count as revenue/cost/profit anywhere in the app (matches the source sheet's totals).
# The funnel endpoint is the sole exception — it shows every stage by definition.
INVOICED = "f.order_status_key = (SELECT order_status_key FROM dim_order_status WHERE label='Invoice')"


# Standard joins every aggregate query builds on.
JOINS = """
FROM fact_transaction f
LEFT JOIN dim_date d     ON d.date_key = f.date_key
LEFT JOIN dim_client c   ON c.client_key = f.client_key
LEFT JOIN dim_service sv ON sv.service_key = f.service_key
LEFT JOIN dim_user u     ON u.user_key = f.user_key
LEFT JOIN dim_brand b    ON b.brand_key = f.brand_key
"""
