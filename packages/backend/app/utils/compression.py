# MIT License

"""Gzip compression middleware for Flask responses.

Standard-library only — no third-party dependencies.
"""

from __future__ import annotations

import gzip
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

# Minimum response size (bytes) to be worth compressing.
MIN_COMPRESS_SIZE = 1024

# Statistics tracking (per-process).
_stats: dict[str, int] = {
    "total_responses": 0,
    "compressed": 0,
    "bytes_before": 0,
    "bytes_after": 0,
}


def get_compression_stats() -> dict[str, int]:
    """Return a snapshot of compression statistics."""
    return dict(_stats)


def reset_compression_stats() -> None:
    """Reset all counters to zero."""
    for k in _stats:
        _stats[k] = 0


def init_compression_middleware(app: Flask) -> None:
    """Register an ``@app.after_request`` hook that gzip-compresses eligible responses."""

    @app.after_request
    def _gzip_after_request(response):
        _stats["total_responses"] += 1

        accept_encoding = (response.headers.get("Vary") or "").lower()

        # Only compress JSON / text payloads
        content_type = response.headers.get("Content-Type", "")
        if not (
            content_type.startswith("application/json")
            or content_type.startswith("text/")
        ):
            return response

        # Check if the client accepts gzip via request headers
        from flask import request

        if "gzip" not in request.headers.get("Accept-Encoding", ""):
            return response

        # Don't double-encode
        if response.headers.get("Content-Encoding") == "gzip":
            return response

        raw_data = response.get_data()

        # Skip tiny payloads
        if len(raw_data) < MIN_COMPRESS_SIZE:
            return response

        # Compress
        buf = BytesIO()
        with gzip.GzipFile(mode="wb", fileobj=buf) as gz:
            gz.write(raw_data)
        compressed = buf.getvalue()

        # Only use compressed data if it is actually smaller
        if len(compressed) < len(raw_data):
            response.set_data(compressed)
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Vary"] = "Accept-Encoding"
            response.headers["Content-Length"] = str(len(compressed))

            _stats["compressed"] += 1
            _stats["bytes_before"] += len(raw_data)
            _stats["bytes_after"] += len(compressed)
        else:
            response.headers["Vary"] = "Accept-Encoding"

        return response
