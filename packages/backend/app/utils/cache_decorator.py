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

"""Flask route caching decorator."""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any

from flask import Flask, Response, current_app, request

from .cache import SimpleCache, get_cache

logger = logging.getLogger("finmind.cache")


def cached_response(timeout: int = 300) -> callable:
    """Decorator that caches Flask route responses.

    Parameters
    ----------
    timeout : int
        Cache TTL in seconds (default 300 = 5 minutes).

    The cache key is derived from ``request.path`` + sorted query args.
    Only **200** responses are cached; errors pass through.
    """

    def decorator(fn: callable) -> callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Response:
            cache: SimpleCache = get_cache()

            params = dict(request.args)
            key = cache.cache_key(request.path, params)

            cached = cache.get(key)
            if cached is not None:
                logger.debug("Cache HIT: %s", request.path)
                return cached

            logger.debug("Cache MISS: %s", request.path)
            response = fn(*args, **kwargs)

            # Only cache successful responses
            if isinstance(response, tuple):
                body, status_code = response[0], response[1]
                headers = response[2] if len(response) > 2 else {}
            elif isinstance(response, Response):
                body = response.get_json()
                status_code = response.status_code
                headers = {}
            else:
                body = response
                status_code = 200
                headers = {}

            if status_code == 200:
                cache.set(key, response, ttl=timeout)

            return response

        return wrapper

    return decorator
