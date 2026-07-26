"""Redis JSON cache for aggregate endpoints + import-job status + function memoization."""
import json
import functools
import hashlib
from decimal import Decimal
import redis
from loguru import logger
from .config import REDIS_URL, CACHE_TTL

_r = redis.from_url(REDIS_URL, decode_responses=True)


def _json_default(o):
    # Decimal -> number (NOT str), so cache-hit responses match cache-miss types.
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def _key(endpoint: str, params: dict) -> str:
    norm = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    return f"agg:{endpoint}:{norm}"


def cached(endpoint: str, params: dict, producer):
    """Return cached JSON for (endpoint, params) or compute+store with TTL."""
    try:
        key = _key(endpoint, params)
        hit = _r.get(key)
        if hit is not None:
            logger.debug("cache hit {}", key)
            return json.loads(hit)
        value = producer()
        _r.setex(key, CACHE_TTL, json.dumps(value, default=_json_default))
        logger.debug("cache miss {} -> stored", key)
        return value
    except redis.RedisError as e:                       # cache is best-effort, never fatal
        logger.warning("redis unavailable ({}), bypassing cache", e)
        return producer()


def invalidate_aggregates():
    """Drop all cached aggregates AND memoized function results after the facts change."""
    try:
        n = 0
        for pattern in ("agg:*", "memo:*"):
            for k in _r.scan_iter(pattern):
                _r.delete(k); n += 1
        logger.info("cache invalidated ({} keys)", n)
    except redis.RedisError as e:
        logger.warning("cache invalidate skipped: {}", e)


# ---- function memoization ----
_SIMPLE = (str, int, float, bool, type(None))


def _hash_args(args, kwargs) -> str:
    """Stable key from JSON-simple args only; non-simple args (e.g. a DB Session) are ignored."""
    parts = [repr(a) for a in args if isinstance(a, _SIMPLE)]
    parts += [f"{k}={v!r}" for k, v in sorted(kwargs.items()) if isinstance(v, _SIMPLE)]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


def memoize(ttl: int = CACHE_TTL, prefix: str = "memo"):
    """Redis-backed memoization for functions whose result depends only on their
    JSON-simple args (str/int/float/bool/None). Non-simple args (Session, ORM objects)
    are excluded from the key — pass the identifying values positionally/by keyword.
    Best-effort: falls back to a live call if Redis is down. Cleared by
    invalidate_aggregates() on import/mutation.

        @memoize(ttl=600)
        def client_scorecard(db, client_id): ...   # keyed by client_id only
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*args, **kwargs):
            try:
                key = f"{prefix}:{fn.__module__}.{fn.__qualname__}:{_hash_args(args, kwargs)}"
                hit = _r.get(key)
                if hit is not None:
                    logger.debug("memoize hit {}", key)
                    return json.loads(hit)
                val = fn(*args, **kwargs)
                _r.setex(key, ttl, json.dumps(val, default=_json_default))
                return val
            except redis.RedisError as e:
                logger.warning("memoize bypass ({}): {}", fn.__qualname__, e)
                return fn(*args, **kwargs)
        return wrap
    return deco


# ---- import-job status ----
def set_job(job_id: str, status: dict):
    try:
        _r.setex(f"job:{job_id}", 3600, json.dumps(status, default=_json_default))
    except redis.RedisError as e:
        logger.warning("job status not stored: {}", e)


def get_job(job_id: str):
    try:
        v = _r.get(f"job:{job_id}")
        return json.loads(v) if v else None
    except redis.RedisError:
        return None


if __name__ == "__main__":  # self-check: key hashing (no Redis needed)
    class _Sess:  # stands in for a DB Session — must be ignored in the key
        pass
    s = _Sess()
    # same simple args -> same key regardless of the ignored Session/instance
    assert _hash_args((s, 5), {}) == _hash_args((_Sess(), 5), {}), "Session must not affect the key"
    # different simple args -> different key
    assert _hash_args((s, 5), {}) != _hash_args((s, 6), {}), "id must affect the key"
    # kwargs order-independent
    assert _hash_args((), {"a": 1, "b": 2}) == _hash_args((), {"b": 2, "a": 1})
    assert len(_hash_args((s, "BEL401"), {})) == 16
    print("cache._hash_args self-check passed")
