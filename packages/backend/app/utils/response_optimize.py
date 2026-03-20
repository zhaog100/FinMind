# MIT License

"""Response payload optimization helpers.

Provides utilities for cleaning, paginating, and serializing API responses.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def clean_response(data: Any) -> Any:
    """Remove ``None`` values and empty strings from dicts/lists recursively."""
    if isinstance(data, dict):
        return {k: clean_response(v) for k, v in data.items() if v is not None and v != ""}
    if isinstance(data, list):
        return [clean_response(item) for item in data]
    return data


def paginate_response(
    items: list,
    page: int,
    page_size: int,
    total: int | None = None,
) -> dict:
    """Wrap a list of items into a standardised pagination envelope.

    Parameters
    ----------
    items:
        The slice of items for the current page.
    page:
        Current 1-based page number.
    page_size:
        Number of items per page.
    total:
        Total item count.  If *None*, ``len(items)`` is used (only accurate
        for single-page results).
    """
    if total is None:
        total = len(items)
    return {
        "data": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
            "has_next": page * page_size < total,
            "has_prev": page > 1,
        },
    }


def datetime_serialize(value: Any) -> Any:
    """Ensure all ``date`` / ``datetime`` objects are ISO-8601 strings (recursive)."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: datetime_serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [datetime_serialize(item) for item in value]
    return value
