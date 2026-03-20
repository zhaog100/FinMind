"""Payee alias management routes for FinMind."""

import re
import logging
from collections import Counter
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import PayeeAlias, Expense

bp = Blueprint("payee_aliases", __name__)
logger = logging.getLogger("finmind.payee_aliases")


@bp.get("")
@jwt_required()
def list_aliases():
    """List all payee aliases for the authenticated user."""
    uid = int(get_jwt_identity())
    aliases = PayeeAlias.query.filter_by(user_id=uid).order_by(PayeeAlias.canonical_name).all()
    return jsonify([a.to_dict() for a in aliases])


@bp.post("")
@jwt_required()
def create_alias():
    """Create a new payee alias."""
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    canonical = (data.get("canonical_name") or "").strip()
    pattern = (data.get("alias_pattern") or "").strip()
    match_type = (data.get("match_type") or "exact").strip()

    if not canonical or not pattern:
        return jsonify({"error": "canonical_name and alias_pattern are required"}), 400

    valid_types = {"exact", "case_insensitive", "contains", "regex"}
    if match_type not in valid_types:
        return jsonify({"error": f"match_type must be one of {valid_types}"}), 400

    if match_type == "regex":
        try:
            re.compile(pattern)
        except re.error as e:
            return jsonify({"error": f"Invalid regex: {e}"}), 400

    alias = PayeeAlias(user_id=uid, canonical_name=canonical, alias_pattern=pattern, match_type=match_type)
    db.session.add(alias)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Alias pattern already exists for this user"}), 409

    return jsonify(alias.to_dict()), 201


@bp.put("/<int:alias_id>")
@jwt_required()
def update_alias(alias_id):
    """Update an existing payee alias."""
    uid = int(get_jwt_identity())
    alias = PayeeAlias.query.filter_by(id=alias_id, user_id=uid).first()
    if not alias:
        return jsonify({"error": "Alias not found"}), 404

    data = request.get_json(silent=True) or {}
    if "canonical_name" in data:
        alias.canonical_name = data["canonical_name"].strip()
    if "alias_pattern" in data:
        alias.alias_pattern = data["alias_pattern"].strip()
    if "match_type" in data:
        valid_types = {"exact", "case_insensitive", "contains", "regex"}
        if data["match_type"] not in valid_types:
            return jsonify({"error": f"match_type must be one of {valid_types}"}), 400
        alias.match_type = data["match_type"]

    if alias.match_type == "regex":
        try:
            re.compile(alias.alias_pattern)
        except re.error as e:
            return jsonify({"error": f"Invalid regex: {e}"}), 400

    db.session.commit()
    return jsonify(alias.to_dict())


@bp.delete("/<int:alias_id>")
@jwt_required()
def delete_alias(alias_id):
    """Delete a payee alias."""
    uid = int(get_jwt_identity())
    alias = PayeeAlias.query.filter_by(id=alias_id, user_id=uid).first()
    if not alias:
        return jsonify({"error": "Alias not found"}), 404
    db.session.delete(alias)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200


@bp.post("/resolve")
@jwt_required()
def resolve_payees():
    """Resolve payee names for expenses using alias rules."""
    uid = int(get_jwt_identity())
    aliases = PayeeAlias.query.filter_by(user_id=uid).all()
    if not aliases:
        return jsonify({"resolved": [], "message": "No aliases configured"})

    rules = []
    for a in aliases:
        try:
            if a.match_type == "regex":
                rules.append((re.compile(a.alias_pattern, re.IGNORECASE), a.canonical_name))
            else:
                rules.append((a,))
        except re.error:
            continue

    expenses = Expense.query.filter_by(user_id=uid).all()
    resolved = []
    for exp in expenses:
        raw = exp.payee or exp.notes or ""
        if not raw.strip():
            continue
        for rule in rules:
            canonical = _match_rule(rule, raw)
            if canonical:
                resolved.append({
                    "expense_id": exp.id,
                    "raw_payee": raw[:100],
                    "resolved_to": canonical,
                })
                break

    return jsonify({"resolved": resolved, "rules_count": len(rules), "expenses_checked": len(expenses)})


@bp.post("/auto-suggest")
@jwt_required()
def auto_suggest():
    """Suggest potential payee aliases based on existing expense data."""
    uid = int(get_jwt_identity())
    expenses = Expense.query.filter_by(user_id=uid).all()

    payees = []
    for exp in expenses:
        raw = (exp.payee or exp.notes or "").strip()
        if raw:
            payees.append(raw.lower())

    # Group by normalized form
    groups = Counter()
    for p in payees:
        # Normalize: lowercase, strip common suffixes
        norm = re.sub(r"[^a-z0-9]", "", p)
        groups[norm] += 1

    # Find potential merges (different strings mapping to same normalized form)
    suggestions = []
    seen = set()
    for exp in expenses:
        raw = (exp.payee or exp.notes or "").strip()
        if not raw or raw in seen:
            continue
        norm = re.sub(r"[^a-z0-9]", "", raw.lower())
        if groups.get(norm, 0) >= 2:
            seen.add(raw)
            # Find the most common variant as canonical
            variants = [e.payee or e.notes for e in expenses if (e.payee or e.notes or "").strip().lower() == raw.lower()]
            if len(variants) > 1:
                canonical = max(Counter(variants).items(), key=lambda x: x[1])[0]
                suggestions.append({
                    "canonical_name": canonical,
                    "alias_pattern": raw,
                    "match_type": "case_insensitive",
                    "count": groups[norm],
                })

    return jsonify({"suggestions": suggestions[:20]})


def _match_rule(rule, raw):
    """Match a payee string against an alias rule."""
    if len(rule) == 1:
        a = rule[0]
        if a.match_type == "exact":
            if raw.lower() == a.alias_pattern.lower():
                return a.canonical_name
        elif a.match_type == "case_insensitive":
            if raw.lower() == a.alias_pattern.lower():
                return a.canonical_name
        elif a.match_type == "contains":
            if a.alias_pattern.lower() in raw.lower():
                return a.canonical_name
    else:
        regex, canonical = rule
        if regex.search(raw):
            return canonical
    return None
