"""Job monitoring and management routes."""

import logging
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, desc

from ..extensions import db
from ..models import JobAttempt, DeadLetter, User
from ..services.job_runner import get_job_stats, process_pending

logger = logging.getLogger("finmind.jobs")

bp = Blueprint("jobs", __name__)


def _require_admin(uid: int) -> bool:
    user = db.session.get(User, uid)
    return user is not None and getattr(user, "role", "USER") == "ADMIN"


@bp.get("/health")
def jobs_health():
    """Lightweight health check for the background job system."""
    from ..observability import Observability

    stats = get_job_stats()
    healthy = stats.get("dead", 0) == 0
    return jsonify(
        status="healthy" if healthy else "degraded",
        stats=stats,
    ), 200 if healthy else 503


@bp.get("")
@jwt_required()
def list_jobs():
    """List recent job attempts. Admin only."""
    uid = int(get_jwt_identity())
    if not _require_admin(uid):
        return jsonify(error="forbidden"), 403

    page = max(1, int(__import__("flask", fromlist=["request"]).request.args.get("page", 1)))
    per_page = min(50, max(1, int(__import__("flask", fromlist=["request"]).request.args.get("per_page", 20))))

    jobs = (
        db.session.query(JobAttempt)
        .order_by(desc(JobAttempt.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    total = db.session.query(func.count(JobAttempt.id)).scalar() or 0
    return jsonify(
        total=total,
        page=page,
        per_page=per_page,
        items=[
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "attempts": j.attempts,
                "max_retries": j.max_retries,
                "last_error": j.last_error,
                "run_after": j.run_after.isoformat() if j.run_after else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ],
    )


@bp.get("/dlq")
@jwt_required()
def list_dlq():
    """List dead-letter entries. Admin only."""
    uid = int(get_jwt_identity())
    if not _require_admin(uid):
        return jsonify(error="forbidden"), 403

    items = (
        db.session.query(DeadLetter)
        .order_by(desc(DeadLetter.created_at))
        .limit(50)
        .all()
    )
    return jsonify(
        total=len(items),
        items=[
            {
                "id": d.id,
                "job_id": d.job_id,
                "job_type": d.job_type,
                "attempts": d.attempts,
                "last_error": d.last_error,
                "reason": d.reason,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in items
        ],
    )


@bp.post("/dlq/<int:dlq_id>/retry")
@jwt_required()
def retry_dlq(dlq_id: int):
    """Re-enqueue a dead-letter job. Admin only."""
    uid = int(get_jwt_identity())
    if not _require_admin(uid):
        return jsonify(error="forbidden"), 403

    import json
    from ..services.job_runner import enqueue

    dlq_entry = db.session.get(DeadLetter, dlq_id)
    if not dlq_entry:
        return jsonify(error="not found"), 404

    payload = json.loads(dlq_entry.payload) if isinstance(dlq_entry.payload, str) else dlq_entry.payload
    new_id = enqueue(
        job_type=dlq_entry.job_type,
        payload=payload,
        dedup_key=f"dlq-retry-{dlq_id}-{dlq_entry.job_id}",
    )
    db.session.delete(dlq_entry)
    db.session.commit()
    logger.info("DLQ retry: dlq_id=%s -> new_job_id=%s", dlq_id, new_id)
    return jsonify(new_job_id=new_id), 200


@bp.post("/process")
@jwt_required()
def process_jobs():
    """Manually trigger job processing. Admin only."""
    uid = int(get_jwt_identity())
    if not _require_admin(uid):
        return jsonify(error="forbidden"), 403

    count = process_pending()
    logger.info("Manual job processing triggered by user=%s processed=%s", uid, count)
    return jsonify(processed=count), 200
