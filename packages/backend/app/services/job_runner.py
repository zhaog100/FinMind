"""
Resilient background job runner with exponential backoff and dead-letter queue.

Jobs are persisted via the JobAttempt model so that retries survive process
restarts.  The public API is intentionally tiny: ``enqueue`` to schedule work
and ``process_pending`` to drain the queue (typically called by a scheduler or
CLI command).
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..extensions import db
from ..models import JobAttempt, DeadLetter

logger = logging.getLogger("finmind.jobs")

# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------
MAX_RETRIES: int = 5
BASE_BACKOFF_SECONDS: float = 2.0
MAX_BACKOFF_SECONDS: float = 300.0  # 5 min cap

# In-memory registry: job_type_name -> callable
_REGISTRY: dict[str, Callable[..., Any]] = {}


def _register(type_name: str, fn: Callable[..., Any]) -> None:
    _REGISTRY[type_name] = fn


def _next_backoff(attempt: int) -> float:
    """Exponential backoff with jitter."""
    backoff = min(BASE_BACKOFF_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS)
    jitter = random.uniform(0, backoff * 0.25)
    return backoff + jitter


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enqueue(
    job_type: str,
    payload: dict[str, Any],
    *,
    run_after: datetime | None = None,
    max_retries: int | None = None,
    dedup_key: str | None = None,
) -> str:
    """Persist a job for async execution.  Returns the new job id."""
    if job_type not in _REGISTRY:
        raise ValueError(f"Unknown job type: {job_type}")

    if dedup_key is not None:
        existing = (
            db.session.query(JobAttempt.id)
            .filter_by(job_type=job_type, dedup_key=dedup_key, status="pending")
            .first()
        )
        if existing is not None:
            logger.info("Dedup: skipping duplicate job dedup_key=%s", dedup_key)
            return str(existing.id)

    job = JobAttempt(
        job_type=job_type,
        payload=json.dumps(payload),
        status="pending",
        max_retries=max_retries if max_retries is not None else MAX_RETRIES,
        run_after=run_after or datetime.now(timezone.utc),
        dedup_key=dedup_key,
    )
    db.session.add(job)
    db.session.commit()
    logger.info("Enqueued job id=%s type=%s", job.id, job_type)
    return str(job.id)


def process_pending(
    *,
    limit: int = 50,
    clock: Callable[[], datetime] | None = None,
) -> int:
    """Drain ready jobs, retrying failures with exponential backoff.

    Returns the number of jobs processed (successfully or permanently failed).
    """
    from ..observability import track_job_event

    now = (clock or datetime.now)(timezone.utc)
    claimed = 0

    try:
        rows = (
            db.session.query(JobAttempt)
            .filter(
                JobAttempt.status.in_(["pending", "retry"]),
                JobAttempt.run_after <= now,
            )
            .order_by(JobAttempt.run_after.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
            .all()
        )
    except Exception:
        # SQLite doesn't support FOR UPDATE; fall back
        rows = (
            db.session.query(JobAttempt)
            .filter(
                JobAttempt.status.in_(["pending", "retry"]),
                JobAttempt.run_after <= now,
            )
            .order_by(JobAttempt.run_after.asc())
            .limit(limit)
            .all()
        )

    for job in rows:
        claimed += 1
        handler = _REGISTRY.get(job.job_type)
        if handler is None:
            logger.error("No handler for job_type=%s id=%s", job.job_type, job.id)
            _move_to_dlq(job, "missing_handler")
            track_job_event(event="dlq", job_type=job.job_type, status="missing_handler")
            continue

        try:
            payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
            handler(payload)
            job.status = "completed"
            job.completed_at = now
            job.attempts += 1
            logger.info("Job completed id=%s type=%s", job.id, job.job_type)
            track_job_event(event="completed", job_type=job.job_type)
        except Exception as exc:
            job.attempts += 1
            job.last_error = str(exc)[:500]
            logger.warning(
                "Job failed id=%s type=%s attempt=%s/%s err=%s",
                job.id,
                job.job_type,
                job.attempts,
                job.max_retries,
                exc,
            )
            if job.attempts >= job.max_retries:
                _move_to_dlq(job, "max_retries_exceeded")
                track_job_event(event="dlq", job_type=job.job_type, status="max_retries")
            else:
                backoff = _next_backoff(job.attempts)
                job.status = "retry"
                job.run_after = now + timedelta(seconds=backoff)
                track_job_event(event="retry", job_type=job.job_type)

    db.session.commit()
    return claimed


def _move_to_dlq(job: JobAttempt, reason: str) -> None:
    job.status = "dead"
    job.completed_at = datetime.now(timezone.utc)
    dlq = DeadLetter(
        job_id=job.id,
        job_type=job.job_type,
        payload=job.payload,
        attempts=job.attempts,
        last_error=job.last_error,
        reason=reason,
    )
    db.session.add(dlq)
    logger.error("Moved job id=%s to DLQ reason=%s", job.id, reason)


# ---------------------------------------------------------------------------
# Built-in job: send_reminder
# ---------------------------------------------------------------------------


def _send_reminder_job(payload: dict[str, Any]) -> None:
    from ..models import Reminder
    from ..services.reminders import send_reminder
    from ..observability import track_reminder_event

    reminder_id = payload.get("reminder_id")
    reminder = db.session.get(Reminder, reminder_id)
    if not reminder:
        raise ValueError(f"Reminder {reminder_id} not found")

    ok = send_reminder(reminder)
    if not ok:
        raise RuntimeError(f"send_reminder returned False for reminder {reminder_id}")

    reminder.sent = True
    track_reminder_event(event="sent", channel=reminder.channel)


_register("send_reminder", _send_reminder_job)


def get_job_stats() -> dict[str, Any]:
    """Return counts grouped by status for monitoring."""
    from sqlalchemy import func

    rows = (
        db.session.query(JobAttempt.status, func.count(JobAttempt.id))
        .group_by(JobAttempt.status)
        .all()
    )
    stats = {status: count for status, count in rows}
    stats["dlq_total"] = db.session.query(func.count(DeadLetter.id)).scalar() or 0
    return stats
