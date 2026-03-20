"""Tests for payee alias management."""

import pytest


def test_create_alias(client, auth_header):
    """Create a payee alias."""
    r = client.post("/api", json={
        "canonical_name": "Amazon",
        "alias_pattern": "AMAZON",
        "match_type": "case_insensitive",
    }, headers=auth_header)
    assert r.status_code == 201
    data = r.get_json()
    assert data["canonical_name"] == "Amazon"
    assert data["alias_pattern"] == "AMAZON"
    assert data["match_type"] == "case_insensitive"
    assert data["id"] is not None


def test_create_alias_exact(client, auth_header):
    """Create an exact match alias."""
    r = client.post("/api", json={
        "canonical_name": "Starbucks",
        "alias_pattern": "STARBUCKS",
        "match_type": "exact",
    }, headers=auth_header)
    assert r.status_code == 201


def test_create_alias_missing_fields(client, auth_header):
    """Reject alias creation without required fields."""
    r = client.post("/api", json={"canonical_name": "Test"}, headers=auth_header)
    assert r.status_code == 400


def test_create_alias_invalid_match_type(client, auth_header):
    """Reject invalid match_type."""
    r = client.post("/api", json={
        "canonical_name": "Test",
        "alias_pattern": "test",
        "match_type": "invalid",
    }, headers=auth_header)
    assert r.status_code == 400


def test_create_alias_invalid_regex(client, auth_header):
    """Reject invalid regex pattern."""
    r = client.post("/api", json={
        "canonical_name": "Test",
        "alias_pattern": "[invalid",
        "match_type": "regex",
    }, headers=auth_header)
    assert r.status_code == 400


def test_create_duplicate_alias(client, auth_header):
    """Reject duplicate alias pattern."""
    client.post("/api", json={"canonical_name": "A", "alias_pattern": "DUP"}, headers=auth_header)
    r = client.post("/api", json={"canonical_name": "B", "alias_pattern": "DUP"}, headers=auth_header)
    assert r.status_code == 409


def test_list_aliases(client, auth_header):
    """List all aliases."""
    client.post("/api", json={"canonical_name": "Amazon", "alias_pattern": "AMZ"}, headers=auth_header)
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_update_alias(client, auth_header):
    """Update an existing alias."""
    r = client.post("/api", json={"canonical_name": "Old", "alias_pattern": "PAT"}, headers=auth_header)
    aid = r.get_json()["id"]
    r2 = client.put(f"/api/{aid}", json={"canonical_name": "New"}, headers=auth_header)
    assert r2.status_code == 200
    assert r2.get_json()["canonical_name"] == "New"


def test_update_alias_not_found(client, auth_header):
    """Return 404 for non-existent alias."""
    r = client.put("/api/99999", json={"canonical_name": "X"}, headers=auth_header)
    assert r.status_code == 404


def test_delete_alias(client, auth_header):
    """Delete an alias."""
    r = client.post("/api", json={"canonical_name": "Del", "alias_pattern": "DEL"}, headers=auth_header)
    aid = r.get_json()["id"]
    r2 = client.delete(f"/api/{aid}", headers=auth_header)
    assert r2.status_code == 200
    # Verify it's gone
    r3 = client.get("/api", headers=auth_header)
    assert all(a["id"] != aid for a in r3.get_json())


def test_delete_alias_not_found(client, auth_header):
    """Return 404 for deleting non-existent alias."""
    r = client.delete("/api/99999", headers=auth_header)
    assert r.status_code == 404


def test_resolve_payees(client, auth_header):
    """Resolve payee names using aliases."""
    # Create aliases
    client.post("/api", json={"canonical_name": "Amazon", "alias_pattern": "amazon", "match_type": "case_insensitive"}, headers=auth_header)
    client.post("/api", json={"canonical_name": "Google", "alias_pattern": "GOOG", "match_type": "contains"}, headers=auth_header)

    r = client.post("/api/resolve", headers=auth_header)
    assert r.status_code == 200
    data = r.get_json()
    assert "resolved" in data
    assert "rules_count" in data


def test_auto_suggest(client, auth_header):
    """Auto-suggest payee aliases."""
    r = client.post("/api/auto-suggest", headers=auth_header)
    assert r.status_code == 200
    data = r.get_json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)


def test_alias_contains_match(client, auth_header):
    """Test contains match type."""
    client.post("/api", json={"canonical_name": "Uber", "alias_pattern": "UBER", "match_type": "contains"}, headers=auth_header)
    r = client.post("/api/resolve", headers=auth_header)
    assert r.status_code == 200


def test_alias_regex_match(client, auth_header):
    """Test regex match type."""
    client.post("/api", json={"canonical_name": "Amazon Prime", "alias_pattern": r"^AMZN.*PRIME$", "match_type": "regex"}, headers=auth_header)
    r = client.get("/api", headers=auth_header)
    assert r.status_code == 200
