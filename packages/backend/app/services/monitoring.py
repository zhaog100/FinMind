"""Job monitoring & metrics collection."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..extensions import redis_client
from .job_manager import JobManager, JobStatus, JOBS_KEY_PREFIX, _utcnow

logger = logging.getLogger(__name__)

METRICS_KEY = "finmind:jobs:metrics"


@dataclass
class JobMetrics:
    total_submitted: int = 0
    total_success: int = 0
    total_failed: int = 0
    total_retried: int = 0
    avg_duration_seconds: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_submitted": self.total_submitted,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "total_retried": self.total_retried,
            "avg_duration_seconds": round(self.avg_duration_seconds, 3),
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
        }


class JobMonitor:
    """Collects and exports job execution metrics from Redis."""

    def __init__(self, manager: JobManager | None = None):
        self._manager = manager or JobManager()
        self._redis = self._manager._redis

    def get_metrics(self) -> JobMetrics:
        jobs = self._manager.list_all()
        metrics = JobMetrics(total_submitted=len(jobs))

        total_duration = 0.0
        duration_count = 0

        for job in jobs:
            if job.status == JobStatus.SUCCESS:
                metrics.total_success += 1
            elif job.status == JobStatus.FAILED:
                metrics.total_failed += 1
            elif job.status == JobStatus.RETRYING:
                metrics.total_retried += 1

            if job.started_at and job.finished_at:
                try:
                    start = datetime.fromisoformat(job.started_at)
                    end = datetime.fromisoformat(job.finished_at)
                    total_duration += (end - start).total_seconds()
                    duration_count += 1
                except (ValueError, TypeError):
                    pass

        metrics.avg_duration_seconds = (
            total_duration / duration_count if duration_count > 0 else 0.0
        )

        completed = metrics.total_success + metrics.total_failed
        if completed > 0:
            metrics.success_rate = metrics.total_success / completed
            metrics.failure_rate = metrics.total_failed / completed

        return metrics

    def export_dict(self) -> dict:
        return self.get_metrics().to_dict()

    def export_json(self) -> str:
        return json.dumps(self.export_dict(), indent=2)
