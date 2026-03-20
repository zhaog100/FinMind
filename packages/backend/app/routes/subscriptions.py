import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import Expense, Subscription

bp = Blueprint("subscriptions", __name__)
logger = logging.getLogger("finmind.subscriptions")

FREQUENCY_CANDIDATES = [7, 14, 30, 90, 365]
AMOUNT_TOLERANCE = Decimal("0.05")  # ±5%
DAY_TOLERANCE = 3


def _amount_similar(a: Decimal, b: Decimal) -> bool:
    if a == 0:
        return b == 0
    return abs(a - b) / a <= AMOUNT_TOLERANCE


def _best_frequency(dates: list) -> int:
    """Pick the most common interval that matches a known frequency candidate."""
    if len(dates) < 2:
        return None
    intervals = []
    for i in range(1, len(dates)):
        intervals.append((dates[i] - dates[i - 1]).days)
    counts = defaultdict(int)
    for iv in intervals:
        for cand in FREQUENCY_CANDIDATES:
            if abs(iv - cand) <= DAY_TOLERANCE:
                counts[cand] += 1
                break
    if not counts:
        return None
    return max(counts, key=counts.get)


@bp.post("/detect")
@jwt_required()
def detect_subscriptions():
    uid = int(get_jwt_identity())
    expenses = (
        Expense.query.filter_by(user_id=uid)
        .order_by(Expense.spent_at.asc())
        .all()
    )
    if not expenses:
        return jsonify([])

    # Group by normalized notes (case-insensitive, stripped)
    groups = defaultdict(list)
    for e in expenses:
        key = (e.notes or "").strip().lower() or None
        groups[key].append(e)

    suggestions = []
    for key, exps in groups.items():
        if len(exps) < 2:
            continue

        dates = [e.spent_at if isinstance(e.spent_at, date) else e.spent_at.date() for e in exps]
        amounts = [e.amount for e in exps]

        # Check amounts are similar
        median_amt = sorted(amounts)[len(amounts) // 2]
        if not all(_amount_similar(a, median_amt) for a in amounts):
            continue

        freq = _best_frequency(dates)
        if freq is None:
            continue

        # Check if already exists
        existing = Subscription.query.filter_by(
            user_id=uid, merchant_hint=key, is_active=True
        ).first()
        if existing:
            continue

        name = key.title() if key else "Unknown"
        suggestions.append(
            {
                "name": name,
                "merchant_hint": key,
                "typical_amount": str(median_amt),
                "frequency_days": freq,
                "currency": exps[0].currency or "INR",
                "occurrences": len(exps),
                "first_seen": str(dates[0]),
                "last_seen": str(dates[-1]),
            }
        )

    return jsonify(suggestions), 200


@bp.get("")
@jwt_required()
def list_subscriptions():
    uid = int(get_jwt_identity())
    subs = Subscription.query.filter_by(user_id=uid).order_by(Subscription.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "merchant_hint": s.merchant_hint,
                "typical_amount": str(s.typical_amount) if s.typical_amount else None,
                "frequency_days": s.frequency_days,
                "currency": s.currency,
                "is_active": s.is_active,
                "is_confirmed": s.is_confirmed,
                "first_seen": str(s.first_seen) if s.first_seen else None,
                "last_seen": str(s.last_seen) if s.last_seen else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in subs
        ]
    ), 200


@bp.put("/<int:sub_id>")
@jwt_required()
def update_subscription(sub_id):
    uid = int(get_jwt_identity())
    sub = Subscription.query.filter_by(id=sub_id, user_id=uid).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ("name", "merchant_hint", "currency"):
        if field in data:
            setattr(sub, field, data[field])
    if "typical_amount" in data:
        sub.typical_amount = Decimal(data["typical_amount"]) if data["typical_amount"] is not None else None
    if "frequency_days" in data:
        sub.frequency_days = int(data["frequency_days"]) if data["frequency_days"] is not None else None
    if "is_active" in data:
        sub.is_active = bool(data["is_active"])
    if "is_confirmed" in data:
        sub.is_confirmed = bool(data["is_confirmed"])
    db.session.commit()
    return jsonify({"id": sub.id, "message": "Updated"}), 200


@bp.delete("/<int:sub_id>")
@jwt_required()
def delete_subscription(sub_id):
    uid = int(get_jwt_identity())
    sub = Subscription.query.filter_by(id=sub_id, user_id=uid).first_or_404()
    db.session.delete(sub)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


@bp.get("/upcoming")
@jwt_required()
def upcoming_subscriptions():
    uid = int(get_jwt_identity())
    today = date.today()
    subs = Subscription.query.filter_by(user_id=uid, is_active=True).all()
    upcoming = []
    for s in subs:
        if not s.last_seen or not s.frequency_days:
            continue
        next_date = s.last_seen + timedelta(days=s.frequency_days)
        days_until = (next_date - today).days
        if days_until >= -1:
            upcoming.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "typical_amount": str(s.typical_amount) if s.typical_amount else None,
                    "currency": s.currency,
                    "predicted_date": str(next_date),
                    "days_until": days_until,
                }
            )
    upcoming.sort(key=lambda x: x["days_until"])
    return jsonify(upcoming), 200
