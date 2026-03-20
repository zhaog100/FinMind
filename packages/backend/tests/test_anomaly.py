"""Tests for anomaly alerts."""

import pytest


def test_scan_anomalies(client, auth_header):
    r = client.post("/api/scan", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "anomalies_found" in d


def test_list_anomalies(client, auth_header):
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_dismiss_not_found(client, auth_header):
    r = client.post("/api/99999/dismiss", headers=auth_header)
    assert r.status_code == 404


def test_scan_then_list(client, auth_header):
    client.post("/api/scan", headers=auth_header)
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
