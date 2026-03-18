"""Job management API routes."""

from flask import Blueprint, jsonify, request

from ..services.job_manager import JobManager, JobStatus

bp = Blueprint("jobs", __name__)
_manager = JobManager()


@bp.get("/api/jobs")
def list_jobs():
    """List all jobs, optionally filtered by status."""
    status = request.args.get("status")
    if status:
        try:
            jobs = _manager.list_all(JobStatus(status))
        except ValueError:
            return jsonify(error=f"Invalid status: {status}"), 400
    else:
        jobs = _manager.list_all()
    return jsonify([j.to_dict() for j in jobs])


@bp.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    job = _manager.get(job_id)
    if job is None:
        return jsonify(error="Job not found"), 404
    return jsonify(job.to_dict())


@bp.post("/api/jobs/retry/<job_id>")
def retry_job(job_id: str):
    job = _manager.retry(job_id)
    if job is None:
        return jsonify(error="Job not found"), 404
    return jsonify(job.to_dict())


@bp.get("/api/jobs/stats")
def job_stats():
    return jsonify(_manager.stats())


@bp.delete("/api/jobs/failed")
def purge_failed():
    count = _manager.purge_dead_letter()
    return jsonify({"purged": count})


@bp.get("/api/jobs/metrics")
def job_metrics():
    from ..services.monitoring import JobMonitor
    monitor = JobMonitor(_manager)
    return jsonify(monitor.export_dict())
