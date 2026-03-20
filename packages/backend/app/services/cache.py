import json
from typing import Iterable
from ..extensions import redis_client


def monthly_summary_key(user_id: int, ym: str) -> str:
    return f"user:{user_id}:monthly_summary:{ym}"


def categories_key(user_id: int) -> str:
    return f"user:{user_id}:categories"


def upcoming_bills_key(user_id: int) -> str:
    return f"user:{user_id}:upcoming_bills"


def insights_key(user_id: int, ym: str) -> str:
    return f"insights:{user_id}:{ym}"


def dashboard_summary_key(user_id: int, ym: str) -> str:
    return f"user:{user_id}:dashboard_summary:{ym}"


def cache_set(key: str, value, ttl_seconds: int | None = None):
    payload = json.dumps(value)
    if ttl_seconds:
        redis_client.setex(key, ttl_seconds, payload)
    else:
        redis_client.set(key, payload)


def cache_get(key: str):
    raw = redis_client.get(key)
    return json.loads(raw) if raw else None


def cache_delete_patterns(patterns: Iterable[str]):
    for pattern in patterns:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break


# === Smart Caching (Issue #127) ===

_cache_stats = {"hits": 0, "misses": 0}

CACHE_TTL = {
    "dashboard": 300, "analytics": 900, "insights": 1800,
    "categories": 3600, "bills": 600,
}


def cache_get(key: str):
    """Get value from cache, return None on miss."""
    global _cache_stats
    payload = redis_client.get(key)
    if payload:
        _cache_stats["hits"] += 1
        return json.loads(payload)
    _cache_stats["misses"] += 1
    return None


def cache_get_or_set(key: str, factory, ttl_seconds: int | None = None):
    """Cache-aside: get from cache or compute and store."""
    cached = cache_get(key)
    if cached is not None:
        return cached
    value = factory()
    cache_set(key, value, ttl_seconds=ttl_seconds)
    return value


def invalidate_user_caches(user_id: int):
    """Invalidate all caches for a user."""
    for pattern in [f"user:{user_id}:*", f"insights:{user_id}:*"]:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)


def get_cache_stats() -> dict:
    """Return cache hit/miss stats."""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    return {
        "hits": _cache_stats["hits"], "misses": _cache_stats["misses"],
        "hit_rate": round(_cache_stats["hits"] / total * 100, 1) if total else 0,
        "total": total,
    }
