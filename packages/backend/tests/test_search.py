"""Tests for advanced search."""

import pytest
from datetime import date


def test_search_empty(client, auth_header):
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "results" in d
    assert "total" in d


def test_search_with_query(client, auth_header):
    r = client.get("/api?q=test", headers=auth_header)
    assert r.status_code == 200


def test_search_with_amount_filter(client, auth_header):
    r = client.get("/api?min_amount=10&max_amount=100", headers=auth_header)
    assert r.status_code == 200


def test_search_with_date_range(client, auth_header):
    r = client.get("/api?date_from=2025-01-01&date_to=2026-12-31", headers=auth_header)
    assert r.status_code == 200


def test_search_with_expense_type(client, auth_header):
    r = client.get("/api?expense_type=EXPENSE", headers=auth_header)
    assert r.status_code == 200


def test_search_pagination(client, auth_header):
    r = client.get("/api?page=1&per_page=5", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert d["per_page"] == 5


def test_search_invalid_date(client, auth_header):
    r = client.get("/api?date_from=invalid", headers=auth_header)
    assert r.status_code == 200  # should not crash, just ignore
