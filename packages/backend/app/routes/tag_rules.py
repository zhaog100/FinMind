"""Tag rules for auto-categorization of expenses."""

import re
import logging
from decimal import Decimal
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import TagRule, Expense, Category

bp = Blueprint("tag_rules", __name__)
logger = logging.getLogger("finmind.tag_rules")


@bp.get("")
@jwt_required()
def list_rules():
    uid = int(get_jwt_identity())
    rules = TagRule.query.filter_by(user_id=uid).order_by(TagRule.priority.desc()).all()
    return jsonify([r.to_dict() for r in rules])


@bp.post("")
@jwt_required()
def create_rule():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    ct = (data.get("condition_type") or "contains").strip()
    cv = (data.get("condition_value") or "").strip()
    at = (data.get("action_type") or "tag").strip()
    av = (data.get("action_value") or "").strip()
    priority = data.get("priority", 0)

    if not name or not cv or not av:
        return jsonify({"error": "name, condition_value, and action_value are required"}), 400
    valid_ct = {"contains", "exact", "regex", "amount_gt", "amount_lt"}
    if ct not in valid_ct:
        return jsonify({"error": f"condition_type must be one of {valid_ct}"}), 400
    if ct == "regex":
        try:
            re.compile(cv)
        except re.error as e:
            return jsonify({"error": f"Invalid regex: {e}"}), 400
    valid_at = {"tag", "categorize"}
    if at not in valid_at:
        return jsonify({"error": f"action_type must be one of {valid_at}"}), 400

    rule = TagRule(user_id=uid, name=name, condition_type=ct, condition_value=cv,
                   action_type=at, action_value=av, priority=priority)
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@bp.put("/<int:rule_id>")
@jwt_required()
def update_rule(rule_id):
    uid = int(get_jwt_identity())
    rule = TagRule.query.filter_by(id=rule_id, user_id=uid).first()
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    data = request.get_json(silent=True) or {}
    for field in ("name", "condition_value", "action_value"):
        if field in data:
            setattr(rule, field, data[field].strip())
    if "condition_type" in data:
        if data["condition_type"] not in {"contains", "exact", "regex", "amount_gt", "amount_lt"}:
            return jsonify({"error": "Invalid condition_type"}), 400
        rule.condition_type = data["condition_type"]
    if "action_type" in data:
        if data["action_type"] not in {"tag", "categorize"}:
            return jsonify({"error": "Invalid action_type"}), 400
        rule.action_type = data["action_type"]
    if "priority" in data:
        rule.priority = int(data["priority"])
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify(rule.to_dict())


@bp.delete("/<int:rule_id>")
@jwt_required()
def delete_rule(rule_id):
    uid = int(get_jwt_identity())
    rule = TagRule.query.filter_by(id=rule_id, user_id=uid).first()
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    db.session.delete(rule)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


@bp.post("/apply")
@jwt_required()
def apply_rules():
    """Apply tag rules to existing expenses, return matched results."""
    uid = int(get_jwt_identity())
    rules = TagRule.query.filter_by(user_id=uid, is_active=True).order_by(TagRule.priority.desc()).all()
    if not rules:
        return jsonify({"matched": 0, "results": []})

    expenses = Expense.query.filter_by(user_id=uid).all()
    results = []
    matched = 0

    for exp in expenses:
        raw = (exp.notes or exp.payee or "").strip()
        if not raw:
            continue
        for rule in rules:
            if _matches(rule, raw, exp.amount):
                matched += 1
                results.append({
                    "expense_id": exp.id,
                    "rule_name": rule.name,
                    "action": f"{rule.action_type}={rule.action_value}",
                    "matched_field": raw[:80],
                })
                break  # first matching rule wins

    return jsonify({"matched": matched, "results": results[:200], "rules_applied": len(rules)})


def _matches(rule, raw, amount):
    if rule.condition_type == "contains":
        return rule.condition_value.lower() in raw.lower()
    elif rule.condition_type == "exact":
        return raw.lower() == rule.condition_value.lower()
    elif rule.condition_type == "regex":
        try:
            return bool(re.search(rule.condition_value, raw, re.IGNORECASE))
        except re.error:
            return False
    elif rule.condition_type == "amount_gt":
        try:
            return float(amount) > float(rule.condition_value)
        except (ValueError, TypeError):
            return False
    elif rule.condition_type == "amount_lt":
        try:
            return float(amount) < float(rule.condition_value)
        except (ValueError, TypeError):
            return False
    return False
