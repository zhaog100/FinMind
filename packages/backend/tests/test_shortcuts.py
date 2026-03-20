"""Tests for keyboard shortcuts."""

import pytest


def test_list_shortcuts(client, auth_header):
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "builtin" in d
    assert "custom" in d
    assert len(d["builtin"]) >= 8


def test_create_shortcut(client, auth_header):
    r = client.post("/api", json={
        "key": "d", "ctrl": True, "action": "dashboard", "description": "Go to dashboard"
    }, headers=auth_header)
    assert r.status_code == 201


def test_create_conflict_builtin(client, auth_header):
    r = client.post("/api", json={"key": "n", "ctrl": True, "action": "custom_action"}, headers=auth_header)
    assert r.status_code == 409


def test_create_missing_fields(client, auth_header):
    r = client.post("/api", json={"key": "x"}, headers=auth_header)
    assert r.status_code == 400


def test_update_shortcut(client, auth_header):
    r = client.post("/api", json={"key": "p", "ctrl": True, "action": "profile"}, headers=auth_header)
    sid = r.get_json()["id"]
    r2 = client.put(f"/api/{sid}", json={"description": "Go to profile page"}, headers=auth_header)
    assert r2.status_code == 200


def test_delete_shortcut(client, auth_header):
    r = client.post("/api", json={"key": "z", "ctrl": True, "action": "test_action"}, headers=auth_header)
    sid = r.get_json()["id"]
    r2 = client.delete(f"/api/{sid}", headers=auth_header)
    assert r2.status_code == 200


def test_delete_not_found(client, auth_header):
    r = client.delete("/api/99999", headers=auth_header)
    assert r.status_code == 404
