# MIT License
#
# Copyright (c) 2026 FinMind Contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

"""Lightweight in-memory cache with TTL and hit-rate statistics."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any


class SimpleCache:
    """Thread-safe, TTL-based in-memory cache.

    Parameters
    ----------
    default_ttl : int
        Default time-to-live in seconds (default 300).
    max_size : int
        Maximum number of entries.  When exceeded the oldest entry is evicted.
    """

    def __init__(self, default_ttl: int = 300, max_size: int = 1024) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.Lock()
        # Statistics
        self._hits = 0
        self._misses = 0

    # -- core operations ---------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return cached value or *None* if missing / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store *value* under *key* with an optional *ttl* (seconds)."""
        if ttl is None:
            ttl = self._default_ttl
        with self._lock:
            if key not in self._store and len(self._store) >= self._max_size:
                self._evict_one()
            self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> bool:
        """Remove *key* from cache.  Returns ``True`` if the key existed."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> int:
        """Remove all entries.  Returns the number of entries removed."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    # -- key helpers -------------------------------------------------------

    @staticmethod
    def cache_key(endpoint: str, params: dict | None = None) -> str:
        """Build a deterministic cache key from *endpoint* and *params*.

        Parameters are JSON-serialised (sorted keys) and SHA-256 hashed so
        the key length stays bounded regardless of input size.
        """
        raw = endpoint
        if params:
            raw += "?" + json.dumps(params, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    # -- statistics --------------------------------------------------------

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "size": len(self._store),
        }

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0

    # -- internals ---------------------------------------------------------

    def _evict_one(self) -> None:
        """Evict the entry closest to expiration (simplest valid strategy)."""
        if not self._store:
            return
        oldest_key = min(
            self._store,
            key=lambda k: self._store[k][1],  # earliest expiry
        )
        del self._store[oldest_key]

    def cleanup_expired(self) -> int:
        """Remove all expired entries.  Returns count removed."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            expired = [
                k for k, (_, exp) in self._store.items() if exp <= now
            ]
            for k in expired:
                del self._store[k]
                removed += 1
        return removed


# Module-level singleton used by the decorator
_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Return the module-level ``SimpleCache`` singleton."""
    return _cache
