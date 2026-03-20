"""Resilient background job retry with exponential backoff and monitoring."""
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger("finmind.job_retry")


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEAD = "dead"


class RetryPolicy:
    """Configurable retry policy with exponential backoff."""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        dead_letter_threshold: int = 0,  # 0 = use max_retries
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.dead_letter_threshold = dead_letter_threshold or max_retries

    def get_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
        if self.jitter:
            import random
            delay *= random.uniform(0.5, 1.5)
        return delay


# In-memory job store (swap for Redis/DB in production)
_jobs: dict[str, dict] = {}
_policies: dict[str, RetryPolicy] = {}
_metrics: dict[str, dict] = {
    "total_submitted": 0,
    "total_success": 0,
    "total_failed": 0,
    "total_dead_letter": 0,
    "by_queue": {},
}

DEFAULT_POLICY = RetryPolicy()


def register_policy(name: str, policy: RetryPolicy):
    """Register a named retry policy."""
    _policies[name] = policy


def get_policy(name: str | None = None) -> RetryPolicy:
    return _policies.get(name or "default", DEFAULT_POLICY)


def submit_job(
    func,
    args: tuple = (),
    kwargs: dict | None = None,
    queue: str = "default",
    policy_name: str | None = None,
    job_id: str | None = None,
    description: str = "",
) -> str:
    """Submit a job for async execution with retry support."""
    jid = job_id or str(uuid.uuid4())[:8]
    _jobs[jid] = {
        "id": jid,
        "func": func,
        "args": args,
        "kwargs": kwargs or {},
        "queue": queue,
        "policy_name": policy_name,
        "description": description,
        "status": JobStatus.PENDING,
        "attempt": 0,
        "max_retries": get_policy(policy_name).max_retries,
        "last_error": None,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "next_retry_at": None,
        "history": [],
    }
    _metrics["total_submitted"] += 1
    _metrics["by_queue"].setdefault(queue, {"submitted": 0, "success": 0, "failed": 0})
    _metrics["by_queue"][queue]["submitted"] += 1
    logger.info("Job submitted: %s queue=%s desc=%s", jid, queue, description)
    return jid


def execute_job(job_id: str) -> dict:
    """Execute a job with retry logic. Returns final status."""
    job = _jobs.get(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    policy = get_policy(job["policy_name"])
    job["status"] = JobStatus.RUNNING
    job["started_at"] = datetime.utcnow().isoformat()

    while job["attempt"] <= policy.max_retries:
        job["attempt"] += 1
        try:
            result = job["func"](*job["args"], **job["kwargs"])
            job["status"] = JobStatus.SUCCESS
            job["completed_at"] = datetime.utcnow().isoformat()
            job["result"] = repr(result)
            job["history"].append({
                "attempt": job["attempt"],
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
            })
            _metrics["total_success"] += 1
            _metrics["by_queue"][job["queue"]]["success"] += 1
            logger.info("Job %s succeeded on attempt %s", job_id, job["attempt"])
            return job

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            job["last_error"] = error_msg
            job["history"].append({
                "attempt": job["attempt"],
                "status": "failed",
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.warning("Job %s failed attempt %s: %s", job_id, job["attempt"], error_msg)

            if job["attempt"] >= policy.dead_letter_threshold:
                break

            delay = policy.get_delay(job["attempt"])
            job["next_retry_at"] = (datetime.utcnow() + timedelta(seconds=delay)).isoformat()
            time.sleep(delay)

    # All retries exhausted
    job["status"] = JobStatus.DEAD
    job["completed_at"] = datetime.utcnow().isoformat()
    _metrics["total_dead_letter"] += 1
    _metrics["total_failed"] += 1
    _metrics["by_queue"][job["queue"]]["failed"] += 1
    logger.error("Job %s moved to dead letter after %s attempts", job_id, job["attempt"])
    return job


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def list_jobs(queue: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
    jobs = list(_jobs.values())
    if queue:
        jobs = [j for j in jobs if j["queue"] == queue]
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jobs[:limit]


def get_dead_letter_queue(limit: int = 50) -> list[dict]:
    return [j for j in _jobs.values() if j["status"] == JobStatus.DEAD][:limit]


def retry_dead_job(job_id: str) -> dict:
    """Retry a dead-lettered job."""
    job = _jobs.get(job_id)
    if not job or job["status"] != JobStatus.DEAD:
        raise ValueError(f"Job {job_id} not in dead letter queue")
    job["status"] = JobStatus.PENDING
    job["attempt"] = 0
    job["last_error"] = None
    job["history"] = []
    return execute_job(job_id)


def get_metrics() -> dict:
    return {
        **_metrics,
        "active_jobs": len([j for j in _jobs.values() if j["status"] in (JobStatus.PENDING, JobStatus.RUNNING)]),
        "dead_letter_count": len(get_dead_letter_queue()),
        "queues": list({j["queue"] for j in _jobs.values()}),
        "policies": {name: {"max_retries": p.max_retries, "base_delay": p.base_delay} for name, p in _policies.items()},
    }


def purge_jobs(older_than_hours: int = 24):
    """Remove completed/dead jobs older than threshold."""
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    to_remove = [
        jid for jid, j in _jobs.items()
        if j["status"] in (JobStatus.SUCCESS, JobStatus.DEAD)
        and datetime.fromisoformat(j["completed_at"] or "1970-01-01") < cutoff
    ]
    for jid in to_remove:
        del _jobs[jid]
    return len(to_remove)
