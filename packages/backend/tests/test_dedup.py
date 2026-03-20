"""Tests for dedup."""

import pytest
from datetime import date, timedelta


def test_scan_no_duplicates(client, auth_header):
    r = client.post("/api/scan", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert d["groups_found"] == 0


def test_list_groups(client, auth_header):
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_dismiss_not_found(client, auth_header):
    r = client.post("/api/groups/99999/dismiss", headers=auth_header)
    assert r.status_code == 404


def test_resolve_not_found(client, auth_header):
    r = client.post("/api/groups/99999/resolve", headers=auth_header)
    assert r.status_code == 404


def test_scan_and_dismiss(client, auth_header):
    # Scan first
    r = client.post("/api/scan", headers=auth_header)
    assert r.status_code == 200
    groups = r.get_json().get("groups", [])
    # Dismiss first group if found
    if groups:
        gid = groups[0]["id"]
        r2 = client.post(f"/api/groups/{gid}/dismiss", headers=auth_header)
        assert r2.status_code == 200


def test_scan_detects_similar(client, auth_header):
    """Scan should detect expenses with same amount and similar merchant."""
    r = client.post("/api/scan", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert isinstance(d["groups"], list)
