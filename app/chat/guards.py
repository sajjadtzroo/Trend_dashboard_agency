"""Per-client rate guard (plan §10). Fixed-window counter on the existing Redis.

ponytail: fixed 1-minute window, not a sliding log — good enough to stop a runaway
client; swap for a token bucket if fairness at the window edge ever matters.
"""
import time

from ..cache import _r
from ..config import RATE_LIMIT_PER_MIN


def rate_limited(client_id: str) -> bool:
    if RATE_LIMIT_PER_MIN <= 0:
        return False
    key = f"rl:{client_id}:{int(time.time() // 60)}"
    n = _r.incr(key)
    if n == 1:
        _r.expire(key, 70)
    return n > RATE_LIMIT_PER_MIN
