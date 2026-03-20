"""Universal bank statement normalization layer."""

import re
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db

bp = Blueprint("normalize", __name__)
logger = logging.getLogger("finmind.normalize")

# Common bank formats
FORMATS = {
    "csv_standard": {"date_col": 0, "desc_col": 1, "amount_col": 2, "delimiter": ",", "has_header": True},
    "csv_indian": {"date_col": 0, "desc_col": 1, "amount_col": 3, "delimiter": ",", "has_header": True},
    "csv_european": {"date_col": 0, "desc_col": 1, "amount_col": 2, "delimiter": ";", "has_header": True},
    "csv_no_header": {"date_col": 0, "desc_col": 1, "amount_col": 2, "delimiter": ",", "has_header": False},
}


@bp.get("/formats")
@jwt_required()
def list_formats():
    """List supported normalization formats."""
    return jsonify({
        "formats": list(FORMATS.keys()),
        "description": "Each format maps column positions and delimiter for CSV parsing",
    })


@bp.post("/parse")
@jwt_required()
def parse_statement():
    """Parse and normalize a bank statement into unified schema."""
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    content = data.get("content", "").strip()
    fmt = data.get("format", "csv_standard")
    custom_mapping = data.get("mapping")  # optional override

    if not content:
        return jsonify({"error": "content is required"}), 400

    if fmt not in FORMATS and not custom_mapping:
        return jsonify({"error": f"Unknown format. Supported: {list(FORMATS.keys())}"}, 400)

    config = custom_mapping or FORMATS[fmt]
    delimiter = config.get("delimiter", ",")
    has_header = config.get("has_header", True)
    date_col = config.get("date_col", 0)
    desc_col = config.get("desc_col", 1)
    amount_col = config.get("amount_col", 2)

    lines = content.strip().split("\n")
    start = 1 if has_header else 0

    parsed = []
    errors = []
    for i, line in enumerate(lines[start:], start=1):
        try:
            cols = line.split(delimiter)
            if len(cols) < max(date_col, desc_col, amount_col) + 1:
                errors.append({"line": i, "error": "Not enough columns"})
                continue

            raw_date = cols[date_col].strip().strip('"')
            description = cols[desc_col].strip().strip('"')
            raw_amount = cols[amount_col].strip().strip('"')

            # Normalize date
            parsed_date = _normalize_date(raw_date)
            if not parsed_date:
                errors.append({"line": i, "error": f"Invalid date: {raw_date}"})
                continue

            # Normalize amount
            parsed_amount = _normalize_amount(raw_amount)
            if parsed_amount is None:
                errors.append({"line": i, "error": f"Invalid amount: {raw_amount}"})
                continue

            # Determine expense type
            expense_type = "EXPENSE" if parsed_amount < 0 else "INCOME"

            parsed.append({
                "line": i,
                "date": parsed_date,
                "description": description[:255],
                "amount": abs(parsed_amount),
                "expense_type": expense_type,
                "currency": config.get("currency", "INR"),
            })
        except Exception as e:
            errors.append({"line": i, "error": str(e)})

    return jsonify({
        "total_lines": len(lines) - (1 if has_header else 0),
        "parsed": len(parsed),
        "errors": len(errors),
        "transactions": parsed[:500],
        "error_details": errors[:50],
    })


@bp.post("/auto-detect")
@jwt_required()
def auto_detect_format():
    """Auto-detect the format of a bank statement."""
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"error": "content is required"}), 400

    lines = content.strip().split("\n")
    if len(lines) < 2:
        return jsonify({"error": "Not enough lines to detect format"}), 400

    first_line = lines[0]
    sample_line = lines[1]

    # Check delimiter
    if ";" in sample_line and "," not in sample_line:
        delimiter = ";"
    else:
        delimiter = ","

    cols = sample_line.split(delimiter)

    # Check if first line is header
    has_header = any(h in first_line.lower() for h in ["date", "description", "amount", "transaction", "narration"])

    # Guess date column (look for date-like patterns)
    date_col = 0
    desc_col = 1
    amount_col = 2

    for i, col in enumerate(cols):
        col = col.strip().strip('"')
        if re.search(r'\d{2}[-/]\d{2}[-/]\d{2,4}', col):
            date_col = i
        if re.search(r'[-+]?\d+[.,]\d{2}', col) and i != date_col:
            amount_col = i

    # Description is usually the longest text column
    max_len = 0
    for i, col in enumerate(cols):
        if i != date_col and i != amount_col and len(col) > max_len:
            max_len = len(col)
            desc_col = i

    return jsonify({
        "detected": {
            "delimiter": delimiter,
            "has_header": has_header,
            "date_col": date_col,
            "desc_col": desc_col,
            "amount_col": amount_col,
            "likely_format": "csv_european" if delimiter == ";" else "csv_standard",
        },
        "sample_columns": len(cols),
    })


def _normalize_date(raw):
    """Try multiple date formats."""
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y",
               "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%Y%m%d", "%d-%b-%y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_amount(raw):
    """Normalize amount string to float."""
    raw = raw.strip().strip('"').replace(",", "")
    # European format: 1.234,56 → 1234.56
    if re.match(r'^[\d.]+,\d{2}$', raw):
        raw = raw.replace(".", "").replace(",", ".")
    # Negative: (123.45) or -123.45
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        return float(Decimal(raw))
    except (InvalidOperation, ValueError):
        return None
