"""Auth endpoints: login / refresh / logout / me. Tokens ride in HttpOnly cookies."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..config import (ACCESS_TTL, REFRESH_TTL, COOKIE_SECURE, COOKIE_SAMESITE,
                      COOKIE_DOMAIN, COOKIE_REFRESH_PATH)
from .models import LoginIn, UserOut
from .security import issue, verify, revoke, verify_pw
from .deps import get_current_user
from .rate_limit import check_login_rate

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_PATH = COOKIE_REFRESH_PATH
_BAD_CREDS = HTTPException(status_code=401, detail="invalid username or password")


def _set_cookie(resp: Response, name: str, value: str, ttl: int, path: str) -> None:
    resp.set_cookie(name, value, max_age=ttl, path=path, httponly=True,
                    secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, domain=COOKIE_DOMAIN or None)


def _issue_pair(resp: Response, user_id: int, ver: int) -> None:
    _set_cookie(resp, "access_token", issue(user_id, ver, "access"), ACCESS_TTL, "/")
    _set_cookie(resp, "refresh_token", issue(user_id, ver, "refresh"), REFRESH_TTL, _REFRESH_PATH)


def _clear(resp: Response) -> None:
    resp.delete_cookie("access_token", path="/", domain=COOKIE_DOMAIN or None)
    resp.delete_cookie("refresh_token", path=_REFRESH_PATH, domain=COOKIE_DOMAIN or None)


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    check_login_rate(ip, data.username)
    row = db.execute(
        text("SELECT id, username, password_hash, token_version, is_active FROM app_user WHERE username = :u"),
        {"u": data.username},
    ).mappings().first()
    # Always run the Argon2 check (dummy hash when the user is missing) so the
    # response is identical for "no such user" and "wrong password".
    ok = verify_pw(row["password_hash"] if row else None, data.password)
    if not row or not row["is_active"] or not ok:
        logger.info("login failed user={} ip={}", data.username, ip)
        raise _BAD_CREDS
    _issue_pair(response, row["id"], row["token_version"])
    logger.info("login ok user={} ip={}", row["username"], ip)
    return UserOut(id=row["id"], username=row["username"])


@router.post("/refresh", response_model=UserOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    payload = verify(token, "refresh") if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    row = db.execute(
        text("SELECT id, username, token_version, is_active FROM app_user WHERE id = :id"),
        {"id": int(payload["sub"])},
    ).mappings().first()
    if not row or not row["is_active"] or row["token_version"] != payload["ver"]:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    revoke(payload["jti"], "refresh")          # rotate: old refresh token can't be reused
    _issue_pair(response, row["id"], row["token_version"])
    return UserOut(id=row["id"], username=row["username"])


@router.post("/logout")
def logout(request: Request, response: Response, all: int = 0, db: Session = Depends(get_db)):
    access = request.cookies.get("access_token")
    payload = verify(access, "access") if access else None
    if payload:
        revoke(payload["jti"], "access")
        if all:  # revoke every session by bumping the user's token_version
            db.execute(text("UPDATE app_user SET token_version = token_version + 1 WHERE id = :id"),
                       {"id": int(payload["sub"])})
            db.commit()
    rt = request.cookies.get("refresh_token")
    rp = verify(rt, "refresh") if rt else None
    if rp:
        revoke(rp["jti"], "refresh")
    _clear(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], username=user["username"])
