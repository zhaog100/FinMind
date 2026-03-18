"""Resilient background job manager with retry & monitoring support.

Thread-safe job queue backed by Redis.  Supports exponential-backoff retries
and a dead-letter queue for permanently failed tasks.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Coroutine

import redis

from ..extensions import redis_client

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_RETRIES = 5
BACKOFF_BASE = 2  # seconds
BACKOFF_MULTIPLIER = 2
DEAD_LETTER_KEY = "finmind:jobs:dlq"
JOBS_KEY_PREFIX = "finmind:jobs:"
STATS_KEY = "finmind:jobs:stats"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class JobRecord:
    id: str
    name: str
    status: JobStatus = JobStatus.PENDING
    retries: int = 0
    max_retries: int = MAX_RETRIES
    created_at: str = ""
    updated_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    error: str = ""
    result: Any = None

    def __post_init__(self):
        now = _utcnow()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "JobRecord":
        d = dict(d)
        d["status"] = JobStatus(d["status"])
        return cls(**d)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backoff_seconds(retry: int) -> float:
    return BACKOFF_BASE * (BACKOFF_MULTIPLIER ** retry)


# ── JobManager ───────────────────────────────────────────────────────────────

class JobManager:
    """Redis-backed job queue with retry support and dead-letter queue."""

    def __init__(self, redis_conn: redis.Redis | None = None):
        self._redis = redis_conn or redis_client
        self._lock = threading.Lock()

    # ── public API ───────────────────────────────────────────────────────

    def submit(
        self,
        func: Callable[..., Any] | Callable[..., Awaitable[Any]],
        *args: Any,
        name: str | None = None,
        max_retries: int = MAX_RETRIES,
        **kwargs: Any,
    ) -> JobRecord:
        """Submit a job for execution (synchronous).  Returns JobRecord immediately."""
        job = JobRecord(
            id=uuid.uuid4().hex[:12],
            name=name or getattr(func, "__name__", "anonymous"),
            max_retries=max_retries,
        )
        self._save(job)

        def _run():
            self._execute(job, func, args, kwargs)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return job

    async def submit_async(
        self,
        coro_fn: Callable[..., Coroutine],
        *args: Any,
        name: str | None = None,
        max_retries: int = MAX_RETRIES,
        **kwargs: Any,
    ) -> JobRecord:
        job = JobRecord(
            id=uuid.uuid4().hex[:12],
            name=name or getattr(coro_fn, "__name__", "anonymous"),
            max_retries=max_retries,
        )
        self._save(job)
        asyncio.get_event_loop().create_task(
            self._execute_async(job, coro_fn, args, kwargs)
        )
        return job

    def get(self, job_id: str) -> JobRecord | None:
        data = self._redis.get(f"{JOBS_KEY_PREFIX}{job_id}")
        if data:
            return JobRecord.from_dict(json.loads(data))
        return None

    def list_all(self, status: JobStatus | None = None) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        prefix = JOBS_KEY_PREFIX
        for key in self._redis.scan_iter(f"{prefix}*"):
            raw = self._redis.get(key)
            if not raw:
                continue
            job = JobRecord.from_dict(json.loads(raw))
            if status is None or job.status == status:
                jobs.append(job)
        return jobs

    def retry(self, job_id: str) -> JobRecord | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job.status not in (JobStatus.FAILED, JobStatus.RETRYING):
            return job
        job.status = JobStatus.RETRYING
        job.error = ""
        job.retries = 0
        job.updated_at = _utcnow()
        self._save(job)

        # Move out of DLQ if present
        self._redis.srem(DEAD_LETTER_KEY, job_id)

        # Re-execute in background (we don't have the original func, caller
        # should use retry_handler for that).  For API manual retry we just
        # reset status; the caller is expected to re-submit the actual work.
        return job

    def list_dead_letter(self) -> list[JobRecord]:
        job_ids = self._redis.smembers(DEAD_LETTER_KEY)
        return [j for jid in job_ids if (j := self.get(jid)) is not None]

    def purge_dead_letter(self) -> int:
        job_ids = list(self._redis.smembers(DEAD_LETTER_KEY))
        count = 0
        for jid in job_ids:
            self._redis.delete(f"{JOBS_KEY_PREFIX}{jid}")
            self._redis.srem(DEAD_LETTER_KEY, jid)
            count += 1
        return count

    def stats(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for s in JobStatus:
            result[s.value] = 0
        result["total"] = 0
        for job in self.list_all():
            result[job.status.value] += 1
            result["total"] += 1
        return result

    # ── internals ────────────────────────────────────────────────────────

    def _save(self, job: JobRecord) -> None:
        self._redis.set(
            f"{JOBS_KEY_PREFIX}{job.id}",
            json.dumps(job.to_dict()),
        )

    def _execute(
        self,
        job: JobRecord,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> None:
        while True:
            with self._lock:
                job.status = JobStatus.RUNNING
                job.started_at = _utcnow()
                job.updated_at = _utcnow()
                self._save(job)

            try:
                result = func(*args, **kwargs)
                with self._lock:
                    job.status = JobStatus.SUCCESS
                    job.result = str(result) if result is not None else None
                    job.finished_at = _utcnow()
                    job.updated_at = _utcnow()
                    self._save(job)
                return
            except Exception as exc:
                with self._lock:
                    job.retries += 1
                    job.error = str(exc)
                    job.updated_at = _utcnow()

                if job.retries >= job.max_retries:
                    with self._lock:
                        job.status = JobStatus.FAILED
                        job.finished_at = _utcnow()
                        self._save(job)
                        self._redis.sadd(DEAD_LETTER_KEY, job.id)
                    logger.error(
                        "Job %s (%s) failed permanently after %d retries: %s",
                        job.id, job.name, job.retries, exc,
                    )
                    return

                with self._lock:
                    job.status = JobStatus.RETRYING
                    self._save(job)

                wait = _backoff_seconds(job.retries)
                logger.warning(
                    "Job %s (%s) retry %d/%d in %.1fs: %s",
                    job.id, job.name, job.retries, job.max_retries, wait, exc,
                )
                time.sleep(wait)

    async def _execute_async(
        self,
        job: JobRecord,
        coro_fn: Callable[..., Coroutine],
        args: tuple,
        kwargs: dict,
    ) -> None:
        while True:
            with self._lock:
                job.status = JobStatus.RUNNING
                job.started_at = _utcnow()
                job.updated_at = _utcnow()
                self._save(job)

            try:
                result = await coro_fn(*args, **kwargs)
                with self._lock:
                    job.status = JobStatus.SUCCESS
                    job.result = str(result) if result is not None else None
                    job.finished_at = _utcnow()
                    job.updated_at = _utcnow()
                    self._save(job)
                return
            except Exception as exc:
                with self._lock:
                    job.retries += 1
                    job.error = str(exc)
                    job.updated_at = _utcnow()

                if job.retries >= job.max_retries:
                    with self._lock:
                        job.status = JobStatus.FAILED
                        job.finished_at = _utcnow()
                        self._save(job)
                        self._redis.sadd(DEAD_LETTER_KEY, job.id)
                    return

                with self._lock:
                    job.status = JobStatus.RETRYING
                    self._save(job)

                wait = _backoff_seconds(job.retries)
                await asyncio.sleep(wait)


# ── Decorator ────────────────────────────────────────────────────────────────

# Global default manager singleton
_default_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = JobManager()
    return _default_manager


def retry_async(
    max_retries: int = MAX_RETRIES,
    backoff: str = "exponential",
):
    """Decorator that wraps an async function with resilient retry logic.

    Usage::

        @retry_async(max_retries=5, backoff='exponential')
        async def send_notification(user_id, message):
            ...
    """
    manager = get_job_manager()

    def decorator(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await manager.submit_async(fn, *args, name=fn.__name__,
                                              max_retries=max_retries, **kwargs)

        return wrapper

    return decorator


def retry_sync(
    max_retries: int = MAX_RETRIES,
    backoff: str = "exponential",
):
    """Synchronous counterpart of ``retry_async``."""
    manager = get_job_manager()

    def decorator(fn: Callable[..., Any]):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            job = manager.submit(fn, *args, name=fn.__name__,
                                 max_retries=max_retries, **kwargs)
            return job  # returns JobRecord so caller can track

        return wrapper

    return decorator
