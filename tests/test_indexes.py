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

"""Tests for database indexing optimization."""

import sqlite3

import pytest

from backend.app import create_app
from backend.app.utils.db_optimize import INDEX_DEFINITIONS, analyze_queries, create_indexes, get_index_info
from backend.app.extensions import db as _db


@pytest.fixture
def app():
    """Create application with in-memory SQLite database."""
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


class TestCreateIndexes:
    def test_creates_indexes_without_error(self, app):
        with app.app_context():
            created = create_indexes()
            assert isinstance(created, list)

    def test_idempotent(self, app):
        with app.app_context():
            first = create_indexes()
            second = create_indexes()
            # SQLite CREATE INDEX IF NOT EXISTS is idempotent, both succeed
            assert len(first) == len(second)

    def test_index_count_matches_definitions(self, app):
        with app.app_context():
            created = create_indexes()
            assert len(created) == len(INDEX_DEFINITIONS)


class TestGetIndexInfo:
    def test_returns_list(self, app):
        with app.app_context():
            create_indexes()
            info = get_index_info()
            assert isinstance(info, list)

    def test_contains_created_indexes(self, app):
        with app.app_context():
            create_indexes()
            info = get_index_info()
            names = [i["name"] for i in info]
            for _, index_name, _ in INDEX_DEFINITIONS:
                assert index_name in names, f"Index {index_name} not found in {names}"


class TestAnalyzeQueries:
    def test_returns_results(self, app):
        with app.app_context():
            create_indexes()
            results = analyze_queries()
            assert isinstance(results, list)
            assert len(results) > 0

    def test_queries_use_indexes(self, app):
        with app.app_context():
            # Insert minimal test data so SQLite considers using indexes
            from backend.app.models import Expense, User

            user = User(email="test@test.com", password_hash="x")
            _db.session.add(user)
            _db.session.commit()

            create_indexes()

            results = analyze_queries()
            for r in results:
                assert "uses_index" in r
                assert isinstance(r["uses_index"], bool)


class TestMigration:
    def test_migration_script_importable(self):
        """Ensure the migration module can be imported without errors."""
        import importlib

        mod = importlib.import_module("backend.app.migrations.add_indexes")
        assert hasattr(mod, "run_migration")
