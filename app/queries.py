"""Shared query execution helper used by every router.

Kept out of the routers so statements/management don't import from dashboard.
"""
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session


def _coerce(v):
    # Postgres NUMERIC -> Decimal; make it a JSON number so it survives the
    # Redis json round-trip as a number (else charts receive strings).
    return float(v) if isinstance(v, Decimal) else v


def rows(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    return [{k: _coerce(v) for k, v in r._mapping.items()}
            for r in db.execute(text(sql), params or {})]
