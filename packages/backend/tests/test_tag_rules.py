"""Tests for tag rules."""

import pytest


def test_create_rule(client, auth_header):
    r = client.post("/api", json={
        "name": "Coffee shops", "condition_type": "contains",
        "condition_value": "starbucks", "action_type": "tag", "action_value": "coffee"
    }, headers=auth_header)
    assert r.status_code == 201
    d = r.get_json()
    assert d["name"] == "Coffee shops"
    assert d["condition_type"] == "contains"


def test_list_rules(client, auth_header):
    client.post("/api", json={"name": "R1", "condition_value": "x", "action_value": "a"}, headers=auth_header)
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)
    assert len(r.get_json()) >= 1


def test_update_rule(client, auth_header):
    r = client.post("/api", json={"name": "Old", "condition_value": "x", "action_value": "a"}, headers=auth_header)
    rid = r.get_json()["id"]
    r2 = client.put(f"/api/{rid}", json={"name": "New"}, headers=auth_header)
    assert r2.status_code == 200
    assert r2.get_json()["name"] == "New"


def test_delete_rule(client, auth_header):
    r = client.post("/api", json={"name": "Del", "condition_value": "x", "action_value": "a"}, headers=auth_header)
    rid = r.get_json()["id"]
    r2 = client.delete(f"/api/{rid}", headers=auth_header)
    assert r2.status_code == 200


def test_create_rule_missing_fields(client, auth_header):
    r = client.post("/api", json={"name": "Test"}, headers=auth_header)
    assert r.status_code == 400


def test_create_rule_invalid_regex(client, auth_header):
    r = client.post("/api", json={"name": "R", "condition_type": "regex", "condition_value": "[", "action_value": "a"}, headers=auth_header)
    assert r.status_code == 400


def test_apply_rules(client, auth_header):
    client.post("/api", json={"name": "Coffee", "condition_type": "contains", "condition_value": "coffee", "action_value": "cafe"}, headers=auth_header)
    r = client.post("/api/apply", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "matched" in d
    assert "results" in d


def test_apply_amount_rules(client, auth_header):
    client.post("/api", json={"name": "Big", "condition_type": "amount_gt", "condition_value": "100", "action_value": "luxury"}, headers=auth_header)
    r = client.post("/api/apply", headers=auth_header)
    assert r.status_code == 200


def test_delete_not_found(client, auth_header):
    r = client.delete("/api/99999", headers=auth_header)
    assert r.status_code == 404
