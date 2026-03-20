"""Monitoring and management routes for background job retry system."""
import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..services.job_retry import (
    execute_job, get_job, list_jobs, get_dead_letter_queue,
    retry_dead_job, get_metrics, purge_jobs, submit_job,
)

bp = Blueprint("job_retry", __name__)
logger = logging.getLogger("finmind.job_retry_routes")


@bp.get("/jobs")
@jwt_required()
def list_all_jobs():
    queue = request.args.get("queue")
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(list_jobs(queue=queue, status=status, limit=limit))


@bp.get("/jobs/<jid>")
@jwt_required()
def job_detail(jid):
    job = get_job(jid)
    if not job:
        return jsonify(error="job not found"), 404
    return jsonify(job)


@bp.post("/jobs/<jid>/retry")
@jwt_required()
def retry_job(jid):
    try:
        result = retry_dead_job(jid)
        return jsonify(result)
    except ValueError as e:
        return jsonify(error=str(e)), 400


@bp.get("/dead-letter")
@jwt_required()
def dead_letter():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(get_dead_letter_queue(limit=limit))


@bp.get("/metrics")
@jwt_required()
def metrics():
    return jsonify(get_metrics())


@bp.post("/purge")
@jwt_required()
def purge():
    hours = request.args.get("older_than_hours", 24, type=int)
    removed = purge_jobs(hours)
    return jsonify(purged=removed)
