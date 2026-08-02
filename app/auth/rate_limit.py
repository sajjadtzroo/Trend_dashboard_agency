"""Login throttle — fixed window per IP and per username (mirrors the chat guard)."""
import redis
from fastapi import HTTPException

from ..cache import _r
from ..config import LOGIN_MAX, LOGIN_WINDOW


def _hit(key: str) -> int:
    """Increment a windowed counter, return the new count (0 = Redis down, skip)."""
    try:
        n = _r.incr(key)
        if n == 1:
            _r.expire(key, LOGIN_WINDOW)
        return n
    except redis.RedisError:
        return 0  # throttle is best-effort; never lock users out because Redis blipped


def check_login_rate(ip: str, username: str) -> None:
    for key in (f"login:ip:{ip}", f"login:user:{username.lower()}"):
        if _hit(key) > LOGIN_MAX:
            raise HTTPException(status_code=429, detail="too many attempts, try again later")
