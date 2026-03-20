"""Transaction deduplication intelligence."""

import logging
from datetime import timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import DuplicateGroup, DuplicateEntry, Expense

bp = Blueprint("dedup", __name__)
logger = logging.getLogger("finmind.dedup")


@bp.post("/scan")
@jwt_required()
def scan_duplicates():
    uid = int(get_jwt_identity())
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.spent_at).all()

    # Index by amount (group amounts within 0.01)
    amount_groups = defaultdict(list)
    for exp in expenses:
        key = round(float(exp.amount), 2)
        amount_groups[key].append(exp)

    groups_found = []
    for amount_key, exps in amount_groups.items():
        if len(exps) < 2:
            continue
        # Check pairs within 3-day window and similar merchant/notes
        used = set()
        for i in range(len(exps)):
            if exps[i].id in used:
                continue
            cluster = [exps[i]]
            for j in range(i + 1, len(exps)):
                if exps[j].id in used:
                    continue
                date_diff = abs((exps[i].spent_at - exps[j].spent_at).days)
                if date_diff > 3:
                    continue
                if exps[i].source_recurring_id and exps[j].source_recurring_id:
                    if exps[i].source_recurring_id == exps[j].source_recurring_id:
                        continue  # same recurring source, not a duplicate
                merchant_sim = _merchant_similarity(
                    exps[i].payee or exps[i].notes or "",
                    exps[j].payee or exps[j].notes or ""
                )
                if merchant_sim >= 0.5:
                    cluster.append(exps[j])
            if len(cluster) >= 2:
                for e in cluster:
                    used.add(e.id)
                groups_found.append(cluster)

    # Create DuplicateGroup records
    result_groups = []
    for cluster in groups_found:
        group = DuplicateGroup(
            user_id=uid, canonical_expense_id=cluster[0].id,
            status="pending", reason="same_amount_date_merchant"
        )
        db.session.add(group)
        db.session.flush()
        for exp in cluster:
            db.session.add(DuplicateEntry(
                group_id=group.id, expense_id=exp.id, similarity_score=1.0
            ))
        result_groups.append(group.to_dict())

    db.session.commit()
    return jsonify({"groups_found": len(result_groups), "groups": result_groups})


@bp.get("/groups")
@jwt_required()
def list_groups():
    uid = int(get_jwt_identity())
    groups = DuplicateGroup.query.filter_by(user_id=uid).order_by(DuplicateGroup.created_at.desc()).all()
    return jsonify([g.to_dict() for g in groups])


@bp.post("/groups/<int:group_id>/resolve")
@jwt_required()
def resolve_group(group_id):
    uid = int(get_jwt_identity())
    group = DuplicateGroup.query.filter_by(id=group_id, user_id=uid).first()
    if not group:
        return jsonify({"error": "Group not found"}), 404
    entries = DuplicateEntry.query.filter_by(group_id=group_id).all()
    canonical_id = group.canonical_expense_id
    deleted = 0
    for entry in entries:
        if entry.expense_id != canonical_id:
            exp = Expense.query.get(entry.expense_id)
            if exp:
                db.session.delete(exp)
                deleted += 1
    group.status = "resolved"
    db.session.commit()
    return jsonify({"message": f"Kept #{canonical_id}, deleted {deleted} duplicates", "deleted_count": deleted})


@bp.post("/groups/<int:group_id>/dismiss")
@jwt_required()
def dismiss_group(group_id):
    uid = int(get_jwt_identity())
    group = DuplicateGroup.query.filter_by(id=group_id, user_id=uid).first()
    if not group:
        return jsonify({"error": "Group not found"}), 404
    group.status = "dismissed"
    db.session.commit()
    return jsonify({"message": "Dismissed"})


def _merchant_similarity(a, b):
    """Simple merchant similarity: normalized overlap ratio."""
    if not a or not b:
        return 0.0
    a = a.lower().strip()
    b = b.lower().strip()
    if a == b:
        return 1.0
    # Check containment
    if a in b or b in a:
        return 0.8
    # Character overlap
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
