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

"""Database indexing optimization for financial queries (SQLite compatible)."""

import logging
import sqlite3
from typing import Any

from ..extensions import db

logger = logging.getLogger("finmind.db_optimize")

# ---------------------------------------------------------------------------
# Index definitions: (table, index_name, columns_sql)
# ---------------------------------------------------------------------------
INDEX_DEFINITIONS = [
    ("expenses", "ix_expenses_user_id_date", "user_id, spent_at"),
    ("expenses", "ix_expenses_user_id_category_id", "user_id, category_id"),
    ("expenses", "ix_expenses_user_id_created_at", "user_id, created_at DESC"),
    ("categories", "ix_categories_user_id", "user_id"),
    ("bills", "ix_bills_user_id_next_due_date", "user_id, next_due_date"),
    ("reminders", "ix_reminders_user_id_send_at_sent", "user_id, send_at, sent"),
    ("recurring_expenses", "ix_recurring_user_id_active", "user_id, active"),
    ("audit_logs", "ix_audit_logs_user_id_created_at", "user_id, created_at"),
]


def create_indexes() -> list[str]:
    """Create all optimisation indexes. Returns list of created index names."""
    created: list[str] = []
    dialect = db.engine.dialect.name

    for table, index_name, columns_sql in INDEX_DEFINITIONS:
        # PostgreSQL doesn't support DESC in CREATE INDEX column list the same way
        if dialect == "postgresql" and "DESC" in columns_sql:
            columns_sql = columns_sql.replace(" DESC", "")

        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns_sql})"

        try:
            with db.engine.connect() as conn:
                conn.execute(db.text(sql))
                conn.commit()
            created.append(index_name)
            logger.debug("Created index %s on %s", index_name, table)
        except Exception:
            logger.warning("Failed to create index %s (dialect=%s)", index_name, dialect, exc_info=True)

    if created:
        logger.info("Created %d database indexes: %s", len(created), created)
    return created


def get_index_info() -> list[dict[str, Any]]:
    """Return current index information from the database."""
    dialect = db.engine.dialect.name
    rows: list[dict[str, Any]] = []

    if dialect == "sqlite":
        sql = "PRAGMA index_list('expenses')"
        with db.engine.connect() as conn:
            result = conn.execute(db.text(sql))
            for row in result:
                rows.append({"name": row[1], "table": "expenses", "unique": bool(row[2])})
    elif dialect == "postgresql":
        sql = (
            "SELECT indexname, tablename FROM pg_indexes "
            "WHERE schemaname = 'public' ORDER BY tablename, indexname"
        )
        with db.engine.connect() as conn:
            result = conn.execute(db.text(sql))
            for row in result:
                rows.append({"name": row[0], "table": row[1], "unique": False})

    return rows


def analyze_queries() -> list[dict[str, Any]]:
    """Analyze common query patterns using EXPLAIN QUERY PLAN (SQLite only)."""
    dialect = db.engine.dialect.name
    if dialect != "sqlite":
        logger.info("Query analysis only supported for SQLite, current: %s", dialect)
        return []

    patterns = [
        ("expenses_by_user_date", "SELECT * FROM expenses WHERE user_id = 1 ORDER BY spent_at"),
        ("expenses_by_user_category", "SELECT * FROM expenses WHERE user_id = 1 AND category_id = 2"),
        ("expenses_by_user_created", "SELECT * FROM expenses WHERE user_id = 1 ORDER BY created_at DESC"),
        ("bills_by_user_due", "SELECT * FROM bills WHERE user_id = 1 ORDER BY next_due_date"),
        ("reminders_by_user", "SELECT * FROM reminders WHERE user_id = 1 AND sent = 0 ORDER BY send_at"),
    ]

    results: list[dict[str, Any]] = []
    with db.engine.connect() as conn:
        raw = conn.connection  # type: ignore[assignment]
        cursor = raw.cursor()
        for name, query in patterns:
            try:
                cursor.execute(f"EXPLAIN QUERY PLAN {query}")
                plan = [row[4] if len(row) > 4 else str(row) for row in cursor.fetchall()]
                uses_index = any("INDEX" in str(step).upper() for step in plan)
                results.append({"query": name, "uses_index": uses_index, "plan": plan})
            except Exception:
                logger.warning("Failed to analyze query: %s", name, exc_info=True)

    return results
