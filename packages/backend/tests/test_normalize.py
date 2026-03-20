"""Tests for bank statement normalization."""

import pytest


def test_list_formats(client, auth_header):
    r = client.get("/api/formats", headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "formats" in d
    assert len(d["formats"]) >= 4


def test_parse_standard_csv(client, auth_header):
    r = client.post("/api/parse", json={
        "content": "date,description,amount\n2025-01-15,Coffee Shop,-4.50\n2025-01-16,Salary,3000.00",
        "format": "csv_standard"
    }, headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert d["parsed"] == 2


def test_parse_european_csv(client, auth_header):
    r = client.post("/api/parse", json={
        "content": "date;description;amount\n15.01.2025;Kaffee;-4,50\n16.01.2025;Gehalt;3000,00",
        "format": "csv_european"
    }, headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert d["parsed"] == 2


def test_auto_detect(client, auth_header):
    r = client.post("/api/auto-detect", json={
        "content": "date,description,amount\n2025-01-15,Test,-10.00"
    }, headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert "detected" in d
    assert d["detected"]["has_header"] is True


def test_parse_empty(client, auth_header):
    r = client.post("/api/parse", json={"content": "", "format": "csv_standard"}, headers=auth_header)
    assert r.status_code == 400


def test_parse_custom_mapping(client, auth_header):
    r = client.post("/api/parse", json={
        "content": "2025-01-15\nCoffee\n-10.00",
        "mapping": {"date_col": 0, "desc_col": 1, "amount_col": 2, "delimiter": None, "has_header": False}
    }, headers=auth_header)
    assert r.status_code == 200


def test_parse_invalid_amount(client, auth_header):
    r = client.post("/api/parse", json={
        "content": "date,desc,amount\nbad,bad,notanumber",
        "format": "csv_standard"
    }, headers=auth_header)
    assert r.status_code == 200
    d = r.get_json()
    assert d["errors"] > 0
