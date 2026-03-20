import math
from app.services.locale import format_date, format_currency, format_number, parse_locale

def test_parse_locale():
    assert parse_locale("en-IN") == "en-IN"
    assert parse_locale("en-US") == "en-US"
    assert parse_locale("invalid") == "en-IN"
    assert parse_locale(None) == "en-IN"

def test_format_date():
    assert format_date("2026-03-20", "en-IN") == "20-03-2026"
    assert format_date("2026-03-20", "en-US") == "03/20/2026"
    assert format_date("2026-03-20", "ja-JP") == "2026/03/20"
    assert format_date("2026-03-20", "de-DE") == "20.03.2026"
    assert format_date(None) == ""

def test_format_currency_inr():
    assert "₹" in format_currency(1234.56, "INR", "en-IN")
    assert "₹" in format_currency(100000, "INR", "en-IN")

def test_format_currency_usd():
    result = format_currency(1234.56, "USD", "en-US")
    assert result.startswith("$")
    assert "1,234" in result

def test_format_currency_eur():
    result = format_currency(1234.56, "EUR", "de-DE")
    assert result.endswith("€")
    assert "1.234" in result or "1234" in result

def test_format_number():
    assert "," in format_number(1234567, "en-IN")
    assert "," in format_number(1234567, "en-US")
    assert "." in format_number(1234567, "de-DE")

def test_format_number_decimals():
    assert format_number(1234.5, "en-US", decimals=2) == "1,234.50"
    assert format_number(0, "en-US") == "0.00"
