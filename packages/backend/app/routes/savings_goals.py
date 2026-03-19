from datetime import date, datetime
from decimal import Decimal
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import SavingsGoal, SavingsMilestone, GoalStatus, MilestoneType, User
from ..services.cache import cache_delete_patterns
import logging

bp = Blueprint("savings_goals", __name__)
logger = logging.getLogger("finmind.savings_goals")

MILESTONE_THRESHOLDS = [
    (MilestoneType.PERCENT_25, Decimal("0.25")),
    (MilestoneType.PERCENT_50, Decimal("0.50")),
    (MilestoneType.PERCENT_75, Decimal("0.75")),
    (MilestoneType.PERCENT_100, Decimal("1.00")),
]


def _check_milestones(goal: SavingsGoal):
    """Check and create milestone records when thresholds are crossed."""
    if not goal.target_amount or goal.target_amount <= 0:
        return []
    ratio = Decimal(str(goal.current_amount)) / Decimal(str(goal.target_amount))
    newly_achieved = []
    for mtype, threshold in MILESTONE_THRESHOLDS:
        if ratio >= threshold:
            existing = db.session.query(SavingsMilestone).filter_by(
                goal_id=goal.id, milestone_type=mtype
            ).first()
            if existing is None or existing.achieved_at is None:
                if existing is None:
                    ms = SavingsMilestone(
                        goal_id=goal.id,
                        milestone_type=mtype,
                        achieved_at=datetime.utcnow(),
                    )
                    db.session.add(ms)
                else:
                    existing.achieved_at = datetime.utcnow()
                    existing.notified = False
                    ms = existing
                newly_achieved.append(ms)
    # Auto-complete on 100%
    if ratio >= Decimal("1.00") and goal.status == GoalStatus.ACTIVE:
        goal.status = GoalStatus.COMPLETED
    return newly_achieved


def _goal_dict(g: SavingsGoal) -> dict:
    target = float(g.target_amount)
    current = float(g.current_amount)
    pct = round((current / target * 100), 1) if target > 0 else 0
    milestones = (
        db.session.query(SavingsMilestone)
        .filter_by(goal_id=g.id)
        .order_by(SavingsMilestone.achieved_at)
        .all()
    )
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "target_amount": target,
        "current_amount": current,
        "currency": g.currency,
        "progress_percent": pct,
        "status": g.status.value,
        "deadline": g.deadline.isoformat() if g.deadline else None,
        "created_at": g.created_at.isoformat(),
        "updated_at": g.updated_at.isoformat(),
        "milestones": [
            {
                "type": m.milestone_type.value,
                "achieved": m.achieved_at.isoformat() if m.achieved_at else None,
                "notified": m.notified,
            }
            for m in milestones
        ],
    }


@bp.get("")
@jwt_required()
def list_goals():
    uid = int(get_jwt_identity())
    items = (
        db.session.query(SavingsGoal)
        .filter_by(user_id=uid)
        .order_by(SavingsGoal.created_at.desc())
        .all()
    )
    logger.info("List savings goals user=%s count=%s", uid, len(items))
    return jsonify([_goal_dict(g) for g in items])


@bp.post("")
@jwt_required()
def create_goal():
    uid = int(get_jwt_identity())
    user = db.session.get(User, uid)
    data = request.get_json() or {}
    g = SavingsGoal(
        user_id=uid,
        name=data["name"],
        description=data.get("description"),
        target_amount=data["target_amount"],
        currency=data.get("currency") or (user.preferred_currency if user else "INR"),
        deadline=date.fromisoformat(data["deadline"]) if data.get("deadline") else None,
    )
    db.session.add(g)
    db.session.flush()
    # Pre-create milestone placeholders (not achieved)
    for mtype, _ in MILESTONE_THRESHOLDS:
        db.session.add(
            SavingsMilestone(goal_id=g.id, milestone_type=mtype)
        )
    db.session.commit()
    logger.info("Created savings goal id=%s user=%s name=%s", g.id, uid, g.name)
    return jsonify(_goal_dict(g)), 201


@bp.get("/<int:goal_id>")
@jwt_required()
def get_goal(goal_id: int):
    uid = int(get_jwt_identity())
    g = db.session.get(SavingsGoal, goal_id)
    if not g or g.user_id != uid:
        return jsonify(error="not found"), 404
    return jsonify(_goal_dict(g))


@bp.put("/<int:goal_id>")
@jwt_required()
def update_goal(goal_id: int):
    uid = int(get_jwt_identity())
    g = db.session.get(SavingsGoal, goal_id)
    if not g or g.user_id != uid:
        return jsonify(error="not found"), 404
    if g.status != GoalStatus.ACTIVE:
        return jsonify(error="cannot modify inactive goal"), 400
    data = request.get_json() or {}
    for field in ("name", "description", "target_amount", "deadline", "currency"):
        if field in data:
            if field == "deadline":
                g.deadline = (
                    date.fromisoformat(data[field]) if data[field] else None
                )
            else:
                setattr(g, field, data[field])
    db.session.commit()
    logger.info("Updated savings goal id=%s user=%s", g.id, uid)
    cache_delete_patterns([f"user:{uid}:savings_summary:*"])
    return jsonify(_goal_dict(g))


@bp.delete("/<int:goal_id>")
@jwt_required()
def delete_goal(goal_id: int):
    uid = int(get_jwt_identity())
    g = db.session.get(SavingsGoal, goal_id)
    if not g or g.user_id != uid:
        return jsonify(error="not found"), 404
    g.status = GoalStatus.ABANDONED
    db.session.commit()
    logger.info("Abandoned savings goal id=%s user=%s", g.id, uid)
    return jsonify(message="goal abandoned")


@bp.post("/<int:goal_id>/contribute")
@jwt_required()
def contribute(goal_id: int):
    uid = int(get_jwt_identity())
    g = db.session.get(SavingsGoal, goal_id)
    if not g or g.user_id != uid:
        return jsonify(error="not found"), 404
    if g.status != GoalStatus.ACTIVE:
        return jsonify(error="cannot contribute to inactive goal"), 400
    data = request.get_json() or {}
    amount = data.get("amount")
    if amount is None or float(amount) <= 0:
        return jsonify(error="amount must be positive"), 400
    g.current_amount = Decimal(str(g.current_amount)) + Decimal(str(amount))
    newly_achieved = _check_milestones(g)
    db.session.commit()
    logger.info(
        "Contributed amount=%s to goal id=%s user=%s total=%s",
        amount, g.id, uid, g.current_amount,
    )
    cache_delete_patterns([f"user:{uid}:savings_summary:*"])
    result = _goal_dict(g)
    if newly_achieved:
        result["new_milestones"] = [
            m.milestone_type.value for m in newly_achieved
        ]
    return jsonify(result)


@bp.get("/summary")
@jwt_required()
def savings_summary():
    uid = int(get_jwt_identity())
    from ..services.cache import cache_get, cache_set

    cache_key = f"user:{uid}:savings_summary:active"
    cached = cache_get(cache_key)
    if cached:
        return jsonify(cached)

    goals = (
        db.session.query(SavingsGoal)
        .filter_by(user_id=uid, status=GoalStatus.ACTIVE)
        .all()
    )
    total_target = sum(float(g.target_amount) for g in goals)
    total_saved = sum(float(g.current_amount) for g in goals)
    overall_pct = round((total_saved / total_target * 100), 1) if total_target > 0 else 0

    # Next-upcoming milestones across all active goals
    upcoming = (
        db.session.query(SavingsMilestone)
        .join(SavingsGoal, SavingsMilestone.goal_id == SavingsGoal.id)
        .filter(
            SavingsGoal.user_id == uid,
            SavingsGoal.status == GoalStatus.ACTIVE,
            SavingsMilestone.achieved_at.is_(None),
        )
        .order_by(SavingsMilestone.milestone_type)
        .first()
    )

    result = {
        "active_goals": len(goals),
        "total_target": total_target,
        "total_saved": total_saved,
        "overall_progress_percent": overall_pct,
        "next_milestone": {
            "goal_id": upcoming.goal_id,
            "type": upcoming.milestone_type.value,
        }
        if upcoming
        else None,
    }
    cache_set(cache_key, result, ttl_seconds=300)
    return jsonify(result)
