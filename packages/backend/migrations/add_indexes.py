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

"""Migration: add composite indexes for financial queries (SQLite compatible).

Usage (standalone):
    python -m migrations.add_indexes

Usage (from Flask app):
    The create_app factory calls db_optimize.create_indexes() automatically.
"""

import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATION_INDEXES = [
    ("expenses", "ix_expenses_user_id_date", "user_id, spent_at"),
    ("expenses", "ix_expenses_user_id_category_id", "user_id, category_id"),
    ("expenses", "ix_expenses_user_id_created_at", "user_id, created_at DESC"),
    ("categories", "ix_categories_user_id", "user_id"),
    ("bills", "ix_bills_user_id_next_due_date", "user_id, next_due_date"),
    ("reminders", "ix_reminders_user_id_send_at_sent", "user_id, send_at, sent"),
    ("recurring_expenses", "ix_recurring_user_id_active", "user_id, active"),
    ("audit_logs", "ix_audit_logs_user_id_created_at", "user_id, created_at"),
]


def _index_exists(cursor: sqlite3.Cursor, index_name: str) -> bool:
    """Check if an index already exists in SQLite."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None


def run_migration(db_path: str) -> list[str]:
    """Run the index migration against a SQLite database file."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        created: list[str] = []

        for table, index_name, columns_sql in MIGRATION_INDEXES:
            if _index_exists(cursor, index_name):
                logger.info("Index %s already exists, skipping.", index_name)
                continue

            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns_sql})"
            cursor.execute(sql)
            created.append(index_name)
            logger.info("Created index %s on %s (%s)", index_name, table, columns_sql)

        conn.commit()
        logger.info("Migration complete. Created %d indexes.", len(created))
        return created
    finally:
        conn.close()


def main() -> None:
    """CLI entry point."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "instance/finmind.db"
    if not Path(db_path).exists():
        logger.error("Database not found: %s", db_path)
        sys.exit(1)
    run_migration(db_path)


if __name__ == "__main__":
    main()
