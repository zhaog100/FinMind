"""Digest routes — weekly summary and multi-week trends."""

from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..services.digest import calculate_weekly_digest, get_trends

bp = Blueprint("digest", __name__)


@bp.get("/weekly")
@jwt_required()
def weekly_digest():
    uid = int(get_jwt_identity())
    today = date.today()
    default_week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    week_str = (request.args.get("week") or default_week).strip()

    # Basic validation: YYYY-WNN
    parts = week_str.split("-W")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return jsonify(error="invalid week format, expected YYYY-WNN"), 400

    week_num = int(parts[1])
    if not (1 <= week_num <= 53):
        return jsonify(error="week number must be 1-53"), 400

    payload = calculate_weekly_digest(uid, week_str)
    return jsonify(payload)


@bp.get("/trends")
@jwt_required()
def trends():
    uid = int(get_jwt_identity())
    weeks = request.args.get("weeks", "4").strip()
    if not weeks.isdigit() or int(weeks) < 1 or int(weeks) > 52:
        return jsonify(error="weeks must be between 1 and 52"), 400

    data = get_trends(uid, int(weeks))
    return jsonify(data)
