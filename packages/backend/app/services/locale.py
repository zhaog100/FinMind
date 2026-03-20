"""Locale-aware formatting for dates, currencies, and numbers."""
import logging
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

logger = logging.getLogger("finmind.locale")

SUPPORTED_LOCALES = [
    "en-IN", "en-US", "en-GB", "ja-JP", "zh-CN", "de-DE", "fr-FR", "es-ES", "pt-BR",
]

LOCALE_CURRENCY_SYMBOLS = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CNY": "¥", "BRL": "R$", "AUD": "A$", "CAD": "C$",
}

# Locale -> (date_format, number_separator, currency_position)
LOCALE_CONFIG = {
    "en-IN": ("%d-%m-%Y", ",", "prefix"),    # DD-MM-YYYY, Indian lakh format
    "en-US": ("%m/%d/%Y", ",", "prefix"),
    "en-GB": ("%d/%m/%Y", ",", "prefix"),
    "ja-JP": ("%Y/%m/%d", ",", "prefix"),
    "zh-CN": ("%Y-%m-%d", ",", "prefix"),
    "de-DE": ("%d.%m.%Y", ".", "suffix"),    # DD.MM.YYYY
    "fr-FR": ("%d/%m/%Y", " ", "suffix"),
    "es-ES": ("%d/%m/%Y", ".", "prefix"),
    "pt-BR": ("%d/%m/%Y", ".", "prefix"),
}

DEFAULT_LOCALE = "en-IN"
DEFAULT_TIMEZONE = "Asia/Kolkata"


def parse_locale(locale: str | None) -> str:
    if locale and locale in LOCALE_CONFIG:
        return locale
    return DEFAULT_LOCALE


def format_date(d: date | datetime | str | None, locale: str | None = None) -> str:
    """Format date according to locale."""
    if not d:
        return ""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except (ValueError, TypeError):
            return d
    if isinstance(d, datetime):
        d = d.date()
    loc = parse_locale(locale)
    fmt = LOCALE_CONFIG[loc][0]
    return d.strftime(fmt)


def format_currency(amount: float | Decimal, currency: str = "INR", locale: str | None = None) -> str:
    """Format currency with symbol and proper formatting."""
    loc = parse_locale(locale)
    amount = float(amount)
    symbol = LOCALE_CURRENCY_SYMBOLS.get(currency, currency)
    position = LOCALE_CONFIG[loc][2]
    separator = LOCALE_CONFIG[loc][1]

    # Format number with separators
    if loc == "en-IN" and currency == "INR":
        # Indian lakh/crore format: 1,23,456.78
        int_part = int(amount)
        dec_part = abs(round(amount - int_part, 2))
        if dec_part == int(dec_part):
            dec_str = f"{dec_part:.2f}"
        else:
            dec_str = f"{abs(round(amount - int_part, 2)):.2f}"
        s = str(abs(int_part))
        if len(s) <= 3:
            formatted = s
        else:
            formatted = s[-3:]
            s = s[:-3]
            while s:
                formatted = s[-2:] + separator + formatted
                s = s[:-2]
        result = formatted + "." + dec_str.split(".")[1] if "." in dec_str else formatted
        if amount < 0:
            result = "-" + result
    else:
        # Standard format: 123,456.78 or 123.456,78
        dec_places = 0 if currency in ("JPY", "CNY") and amount == int(amount) else 2
        if separator == ".":
            result = f"{amount:,.2f}" if dec_places == 2 else f"{amount:,.0f}"
            result = result.replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            result = f"{amount:,.2f}" if dec_places == 2 else f"{amount:,.0f}"

    if position == "prefix":
        return f"{symbol}{result}"
    else:
        return f"{result} {symbol}"


def format_number(number: float | int | Decimal, locale: str | None = None, decimals: int = 2) -> str:
    """Format number with locale-aware thousand separators."""
    loc = parse_locale(locale)
    n = float(number)
    if loc == "en-IN":
        # Indian format
        int_part = int(n)
        dec_part = round(n - int_part, decimals)
        s = str(abs(int_part))
        if len(s) <= 3:
            formatted = s
        else:
            formatted = s[-3:]
            s = s[:-3]
            while s:
                formatted = s[-2:] + "," + formatted
                s = s[:-2]
        if decimals > 0:
            formatted += f".{abs(dec_part):0{decimals}f}"
        if n < 0:
            formatted = "-" + formatted
        return formatted
    elif LOCALE_CONFIG[loc][1] == ".":
        formatted = f"{n:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    else:
        return f"{n:,.{decimals}f}"


def get_locale_from_user(user) -> str:
    return getattr(user, "locale", None) or DEFAULT_LOCALE
