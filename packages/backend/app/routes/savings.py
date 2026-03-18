from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func

from ..extensions import db
from ..models import SavingsGoal, SavingsTransaction, User

bp = Blueprint("savings", __name__)


# ── Helpers ──────────────────────────────────────────────────────────
def _goal_dict(g: SavingsGoal) -> dict:
    milestones = _milestones(float(g.current_amount), float(g.target_amount))
    days_left = None
    if g.target_date:
        delta = (g.target_date - datetime.utcnow().date()).days
        days_left = max(0, delta)
    return {
        "id": g.id,
        "user_id": g.user_id,
        "name": g.name,
        "target_amount": float(g.target_amount),
        "current_amount": float(g.current_amount),
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "icon": g.icon,
        "color": g.color,
        "milestones": milestones,
        "days_left": days_left,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


def _tx_dict(t: SavingsTransaction) -> dict:
    return {
        "id": t.id,
        "goal_id": t.goal_id,
        "amount": float(t.amount),
        "type": t.type,
        "note": t.note,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _milestones(current: float, target: float) -> list[dict]:
    pct = (current / target * 100) if target else 0
    result = []
    for threshold in [25, 50, 75, 100]:
        result.append({
            "threshold": threshold,
            "reached": pct >= threshold,
            "current_percent": round(pct, 1),
        })
    return result


# ── CRUD ─────────────────────────────────────────────────────────────
@bp.get("")
@jwt_required()
def list_goals():
    uid = int(get_jwt_identity())
    goals = db.session.query(SavingsGoal).filter_by(user_id=uid).order_by(SavingsGoal.created_at.desc()).all()
    return jsonify([_goal_dict(g) for g in goals])


@bp.post("")
@jwt_required()
def create_goal():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400
    try:
        target_amount = Decimal(str(data.get("target_amount", 0)))
    except (InvalidOperation, ValueError):
        return jsonify(error="invalid target_amount"), 400
    target_date = None
    if data.get("target_date"):
        try:
            target_date = datetime.fromisoformat(data["target_date"]).date()
        except (ValueError, TypeError):
            return jsonify(error="invalid target_date"), 400

    goal = SavingsGoal(
        user_id=uid,
        name=name,
        target_amount=target_amount,
        current_amount=Decimal("0"),
        target_date=target_date,
        icon=(data.get("icon") or "🎯")[:10],
        color=(data.get("color") or "#6366f1")[:7],
    )
    db.session.add(goal)
    db.session.commit()
    return jsonify(_goal_dict(goal)), 201


@bp.get("/<int:goal_id>")
@jwt_required()
def get_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.query(SavingsGoal).filter_by(id=goal_id, user_id=uid).first_or_404()
    return jsonify(_goal_dict(goal))


@bp.put("/<int:goal_id>")
@jwt_required()
def update_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.query(SavingsGoal).filter_by(id=goal_id, user_id=uid).first_or_404()
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return jsonify(error="name is required"), 400
        goal.name = name
    if "target_amount" in data:
        try:
            goal.target_amount = Decimal(str(data["target_amount"]))
        except (InvalidOperation, ValueError):
            return jsonify(error="invalid target_amount"), 400
    if "target_date" in data:
        if data["target_date"] is None:
            goal.target_date = None
        else:
            try:
                goal.target_date = datetime.fromisoformat(data["target_date"]).date()
            except (ValueError, TypeError):
                return jsonify(error="invalid target_date"), 400
    if "icon" in data:
        goal.icon = (data["icon"] or "🎯")[:10]
    if "color" in data:
        goal.color = (data["color"] or "#6366f1")[:7]

    goal.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_goal_dict(goal))


@bp.delete("/<int:goal_id>")
@jwt_required()
def delete_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.query(SavingsGoal).filter_by(id=goal_id, user_id=uid).first_or_404()
    db.session.query(SavingsTransaction).filter_by(goal_id=goal_id).delete()
    db.session.delete(goal)
    db.session.commit()
    return jsonify(message="deleted")


# ── Transactions ─────────────────────────────────────────────────────
@bp.post("/<int:goal_id>/contribute")
@jwt_required()
def contribute(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.query(SavingsGoal).filter_by(id=goal_id, user_id=uid).first_or_404()
    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, ValueError):
        return jsonify(error="invalid amount"), 400
    if amount <= 0:
        return jsonify(error="amount must be positive"), 400

    goal.current_amount += amount
    goal.updated_at = datetime.utcnow()
    tx = SavingsTransaction(
        goal_id=goal_id,
        amount=amount,
        type="contribute",
        note=(data.get("note") or "")[:200],
    )
    db.session.add(tx)
    db.session.commit()
    return jsonify(_goal_dict(goal)), 200


@bp.post("/<int:goal_id>/withdraw")
@jwt_required()
def withdraw(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.query(SavingsGoal).filter_by(id=goal_id, user_id=uid).first_or_404()
    data = request.get_json(silent=True) or {}
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, ValueError):
        return jsonify(error="invalid amount"), 400
    if amount <= 0:
        return jsonify(error="amount must be positive"), 400
    if amount > goal.current_amount:
        return jsonify(error="insufficient funds"), 400

    goal.current_amount -= amount
    goal.updated_at = datetime.utcnow()
    tx = SavingsTransaction(
        goal_id=goal_id,
        amount=amount,
        type="withdraw",
        note=(data.get("note") or "")[:200],
    )
    db.session.add(tx)
    db.session.commit()
    return jsonify(_goal_dict(goal)), 200
