"""Redis JSON cache for aggregate endpoints + import-job status."""
import json
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
    """Drop all cached aggregates after the facts change."""
    try:
        n = 0
        for k in _r.scan_iter("agg:*"):
            _r.delete(k); n += 1
        logger.info("cache invalidated ({} keys)", n)
    except redis.RedisError as e:
        logger.warning("cache invalidate skipped: {}", e)


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
