from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..extensions import db
from ..models import SavingsGoal
from ..services.savings_goals import calculate_progress, auto_milestones, check_milestone

bp = Blueprint("savings_goals", __name__)


def _json(goal: SavingsGoal, *, with_progress: bool = False) -> dict:
    d = {
        "id": goal.id,
        "name": goal.name,
        "target_amount": float(goal.target_amount),
        "current_amount": float(goal.current_amount),
        "currency": goal.currency,
        "category": goal.category,
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "milestones": goal.milestones or [],
        "created_at": goal.created_at.isoformat() if goal.created_at else None,
        "updated_at": goal.updated_at.isoformat() if goal.updated_at else None,
    }
    if with_progress:
        d["progress"] = calculate_progress(goal)
    return d


@bp.post("")
@jwt_required()
def create_goal():
    uid = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400
    try:
        target = float(body["target_amount"])
        assert target > 0
    except (KeyError, TypeError, ValueError, AssertionError):
        return jsonify(error="target_amount must be a positive number"), 400

    goal = SavingsGoal(
        user_id=uid,
        name=name,
        target_amount=target,
        current_amount=float(body.get("current_amount", 0)),
        currency=(body.get("currency") or "INR")[:10],
        category=body.get("category"),
        target_date=body.get("target_date"),
        milestones=[],
    )
    db.session.add(goal)
    db.session.flush()
    goal.milestones = auto_milestones(goal)
    db.session.commit()
    return jsonify(_json(goal, with_progress=True)), 201


@bp.get("")
@jwt_required()
def list_goals():
    uid = int(get_jwt_identity())
    goals = (
        db.session.query(SavingsGoal)
        .filter(SavingsGoal.user_id == uid)
        .order_by(SavingsGoal.created_at.desc())
        .all()
    )
    return jsonify([_json(g, with_progress=True) for g in goals])


@bp.get("/summary")
@jwt_required()
def savings_summary():
    uid = int(get_jwt_identity())
    goals = db.session.query(SavingsGoal).filter(SavingsGoal.user_id == uid).all()
    total_saved = sum(float(g.current_amount) for g in goals)
    total_target = sum(float(g.target_amount) for g in goals)
    completed = sum(1 for g in goals if float(g.current_amount) >= float(g.target_amount))
    return jsonify({
        "total_goals": len(goals),
        "completed_goals": completed,
        "active_goals": len(goals) - completed,
        "total_saved": round(total_saved, 2),
        "total_target": round(total_target, 2),
        "overall_percentage": round((total_saved / total_target) * 100, 2) if total_target > 0 else 0,
    })


@bp.get("/<int:goal_id>")
@jwt_required()
def get_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404
    return jsonify(_json(goal, with_progress=True))


@bp.patch("/<int:goal_id>")
@jwt_required()
def update_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404
    body = request.get_json(silent=True) or {}
    for field in ("name", "currency", "category", "target_date"):
        if field in body:
            setattr(goal, field, body[field])
    if "target_amount" in body:
        try:
            val = float(body["target_amount"])
            assert val > 0
            goal.target_amount = val
        except (TypeError, ValueError, AssertionError):
            return jsonify(error="target_amount must be a positive number"), 400
    if "current_amount" in body:
        goal.current_amount = float(body["current_amount"])
    goal.updated_at = datetime.utcnow()
    goal.milestones = auto_milestones(goal)
    db.session.commit()
    return jsonify(_json(goal, with_progress=True))


@bp.delete("/<int:goal_id>")
@jwt_required()
def delete_goal(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404
    db.session.delete(goal)
    db.session.commit()
    return jsonify(message="deleted")


@bp.post("/<int:goal_id>/contribute")
@jwt_required()
def contribute(goal_id: int):
    uid = int(get_jwt_identity())
    goal = db.session.get(SavingsGoal, goal_id)
    if not goal or goal.user_id != uid:
        return jsonify(error="not found"), 404
    body = request.get_json(silent=True) or {}
    try:
        amount = float(body["amount"])
        assert amount > 0
    except (KeyError, TypeError, ValueError, AssertionError):
        return jsonify(error="amount must be a positive number"), 400
    goal.current_amount = round(float(goal.current_amount) + amount, 2)
    goal.updated_at = datetime.utcnow()
    result = check_milestone(goal)
    db.session.commit()
    resp = _json(goal, with_progress=True)
    resp["milestone_event"] = result
    return jsonify(resp)
