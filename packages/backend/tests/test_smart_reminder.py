"""Tests for smart reminder timing."""

import pytest


def test_insights(client, auth_header):
    r = client.get("/api/insights", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "suggestions" in d


def test_optimal_times(client, auth_header):
    r = client.get("/api/optimal-times", headers=auth_header)
    assert r.status_code == 200


def test_insights_no_data(client, auth_header):
    # Should return gracefully even with no expenses
    r = client.get("/api/insights", headers=auth_header)
    assert r.status_code == 200
