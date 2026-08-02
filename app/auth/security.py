"""Password hashing (Argon2id) + JWT issue/verify against a Redis allowlist.

Sync throughout, mirroring the rest of the app. A token is valid only if its
sha256 still lives in Redis (`at:{jti}` / `rt:{jti}`) — that's what makes logout
and revocation instant, which stateless JWT alone can't do. Redis stores the
*hash*, never the token, so a Redis dump can't be replayed.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import redis
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from ..cache import _r
from ..config import JWT_SECRET, ACCESS_TTL, REFRESH_TTL

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
# Verified against when the user doesn't exist, so timing/branches match a real
# check — prevents username enumeration via response time.
_DUMMY_HASH = _ph.hash("timing-equalizer")

_TTL = {"access": ACCESS_TTL, "refresh": REFRESH_TTL}
_PREFIX = {"access": "at", "refresh": "rt"}


def hash_pw(pw: str) -> str:
    return _ph.hash(pw)


def verify_pw(stored_hash: str, pw: str) -> bool:
    try:
        return _ph.verify(stored_hash or _DUMMY_HASH, pw)
    except Argon2Error:
        return False


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(user_id: int, ver: int, typ: str) -> str:
    """Mint a signed token and record its hash in the Redis allowlist."""
    jti = uuid4().hex
    now = datetime.now(timezone.utc)
    ttl = _TTL[typ]
    token = jwt.encode(
        {"sub": str(user_id), "jti": jti, "typ": typ, "ver": ver,
         "iat": now, "exp": now + timedelta(seconds=ttl)},
        JWT_SECRET, algorithm="HS256",
    )
    _r.setex(f"{_PREFIX[typ]}:{jti}", ttl, _sha(token))  # raises if Redis down -> login fails closed
    return token


def verify(token: str, typ: str) -> dict | None:
    """Return the payload iff signature, type, and Redis allowlist all check out."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != typ:
        return None
    try:
        stored = _r.get(f"{_PREFIX[typ]}:{payload['jti']}")
    except redis.RedisError:
        return None  # can't confirm the allowlist -> deny (fail closed)
    if not stored or not hmac.compare_digest(stored, _sha(token)):
        return None
    return payload


def revoke(jti: str, typ: str) -> None:
    try:
        _r.delete(f"{_PREFIX[typ]}:{jti}")
    except redis.RedisError:
        pass
