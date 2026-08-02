"""`get_current_user` — the dependency that gates every protected route."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from .security import verify

_UNAUTH = HTTPException(status_code=401, detail="not authenticated")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise _UNAUTH
    payload = verify(token, "access")
    if not payload:
        raise _UNAUTH
    row = db.execute(
        text("SELECT id, username, token_version, is_active FROM app_user WHERE id = :id"),
        {"id": int(payload["sub"])},
    ).mappings().first()
    # token_version mismatch => password change / logout-all invalidated this token
    if not row or not row["is_active"] or row["token_version"] != payload["ver"]:
        raise _UNAUTH
    return dict(row)
