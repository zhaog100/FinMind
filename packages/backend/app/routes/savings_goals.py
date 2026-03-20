import logging
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import SavingsGoal, GoalContribution, User

bp = Blueprint("savings_goals", __name__)
logger = logging.getLogger("finmind.savings_goals")

MILESTONE_MARKS = [25, 50, 75, 100]


def _goal_to_dict(g):
    d = {
        "id": g.id, "name": g.name,
        "target_amount": float(g.target_amount),
        "current_amount": float(g.current_amount),
        "currency": g.currency, "category": g.category,
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "milestones": json.loads(g.milestones) if g.milestones else [],
        "progress_percent": _calc_progress(g),
        "remaining": max(0, float(g.target_amount - g.current_amount)),
        "days_left": (g.target_date - date.today()).days if g.target_date else None,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }
    return d


def _calc_progress(g):
    if g.target_amount <= 0:
        return 0
    return round(float(g.current_amount) / float(g.target_amount) * 100, 1)


def _check_milestones(g):
    progress = _calc_progress(g)
    new = []
    for mark in MILESTONE_MARKS:
        key = f"{mark}%"
        if key not in (json.loads(g.milestones) if g.milestones else []) and progress >= mark:
            new.append(key)
    if new:
        g.milestones = list((json.loads(g.milestones) if g.milestones else []) + new)
    return new


@bp.get("")
@jwt_required()
def list_goals():
    uid = int(get_jwt_identity())
    goals = db.session.query(SavingsGoal).filter_by(user_id=uid).order_by(SavingsGoal.created_at.desc()).all()
    return jsonify([_goal_to_dict(g) for g in goals])


@bp.get("/summary")
@jwt_required()
def goals_summary():
    uid = int(get_jwt_identity())
    goals = db.session.query(SavingsGoal).filter_by(user_id=uid).all()
    total_target = sum(float(g.target_amount) for g in goals)
    total_saved = sum(float(g.current_amount) for g in goals)
    completed = sum(1 for g in goals if _calc_progress(g) >= 100)
    active = len(goals) - completed
    return jsonify({
        "total_goals": len(goals), "completed": completed, "active": active,
        "total_target": total_target, "total_saved": total_saved,
        "overall_progress": round(total_saved / total_target * 100, 1) if total_target else 0,
    })


@bp.get("/<int:gid>")
@jwt_required()
def get_goal(gid):
    uid = int(get_jwt_identity())
    g = db.session.query(SavingsGoal).filter_by(id=gid, user_id=uid).first()
    if not g:
        return jsonify(error="goal not found"), 404
    contributions = db.session.query(GoalContribution).filter_by(goal_id=gid).order_by(GoalContribution.created_at.desc()).limit(20).all()
    data = _goal_to_dict(g)
    data["recent_contributions"] = [{"id": c.id, "amount": float(c.amount), "note": c.note, "created_at": c.created_at.isoformat()} for c in contributions]
    return jsonify(data)


@bp.post("")
@jwt_required()
def create_goal():
    uid = int(get_jwt_identity())
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name required"), 400
    try:
        target = Decimal(str(data.get("target_amount", 0)))
    except (InvalidOperation, ValueError):
        return jsonify(error="invalid target_amount"), 400
    if target <= 0:
        return jsonify(error="target_amount must be positive"), 400
    user = db.session.get(User, uid)
    g = SavingsGoal(
        user_id=uid, name=name, target_amount=target,
        current_amount=Decimal(0), currency=user.preferred_currency if user else "INR",
        category=data.get("category"), target_date=data.get("target_date"),
        milestones=[],
    )
    db.session.add(g)
    db.session.commit()
    logger.info("Goal created user=%s goal=%s", uid, g.id)
    return jsonify(_goal_to_dict(g)), 201


@bp.patch("/<int:gid>")
@jwt_required()
def update_goal(gid):
    uid = int(get_jwt_identity())
    g = db.session.query(SavingsGoal).filter_by(id=gid, user_id=uid).first()
    if not g:
        return jsonify(error="goal not found"), 404
    data = request.get_json() or {}
    for field in ("name", "category", "target_date"):
        if field in data:
            setattr(g, field, data[field])
    if "target_amount" in data:
        try:
            g.target_amount = Decimal(str(data["target_amount"]))
        except (InvalidOperation, ValueError):
            return jsonify(error="invalid target_amount"), 400
    g.updated_at = date.today()
    db.session.commit()
    return jsonify(_goal_to_dict(g))


@bp.delete("/<int:gid>")
@jwt_required()
def delete_goal(gid):
    uid = int(get_jwt_identity())
    g = db.session.query(SavingsGoal).filter_by(id=gid, user_id=uid).first()
    if not g:
        return jsonify(error="goal not found"), 404
    db.session.delete(g)
    db.session.commit()
    return jsonify(deleted=True), 200


@bp.post("/<int:gid>/contribute")
@jwt_required()
def contribute(gid):
    uid = int(get_jwt_identity())
    g = db.session.query(SavingsGoal).filter_by(id=gid, user_id=uid).first()
    if not g:
        return jsonify(error="goal not found"), 404
    data = request.get_json() or {}
    try:
        amount = Decimal(str(data.get("amount", 0)))
    except (InvalidOperation, ValueError):
        return jsonify(error="invalid amount"), 400
    if amount <= 0:
        return jsonify(error="amount must be positive"), 400
    c = GoalContribution(goal_id=gid, amount=amount, note=data.get("note"))
    db.session.add(c)
    g.current_amount += amount
    g.updated_at = date.today()
    new_milestones = _check_milestones(g)
    db.session.commit()
    result = _goal_to_dict(g)
    if new_milestones:
        result["milestone_achieved"] = new_milestones
    logger.info("Contribution goal=%s amount=%s", gid, amount)
    return jsonify(result), 200
