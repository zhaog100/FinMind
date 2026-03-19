"""Tests for background job runner: retry, DLQ, health, dedup."""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.services.job_runner import (
    MAX_RETRIES,
    enqueue,
    get_job_stats,
    process_pending,
    _REGISTRY,
    _next_backoff,
)
from app.models import JobAttempt, DeadLetter, User


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

FAILURE_COUNT_KEY = "_test_failure_count"


class _FlakyHandler:
    """Handler that fails N times then succeeds."""

    def __init__(self, fail_times: int = 2):
        self.fail_times = fail_times
        self.call_count = 0

    def __call__(self, payload: dict):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise RuntimeError(f"synthetic failure #{self.call_count}")


def _always_fail(payload: dict):
    raise RuntimeError("permanent failure")


def _always_succeed(payload: dict):
    payload.setdefault("calls", []).append("ok")


@pytest.fixture(autouse=True)
def _register_test_handlers():
    """Register / cleanup test handlers."""
    old = dict(_REGISTRY)
    _REGISTRY["test_flaky"] = _FlakyHandler()
    _REGISTRY["test_fail"] = _always_fail
    _REGISTRY["test_ok"] = _always_succeed
    yield
    _REGISTRY.clear()
    _REGISTRY.update(old)


def _freeze_clock(t: datetime):
    """Return a callable usable as clock= argument."""
    return lambda: t


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestNextBackoff:
    def test_increases_exponentially(self):
        b0 = _next_backoff(0)
        b1 = _next_backoff(1)
        assert b1 > b0

    def test_caps_at_max(self):
        b = _next_backoff(100)
        assert b <= 300.0 + 75.0  # max + 25% jitter

    def test_includes_jitter(self):
        """Two calls with same attempt should differ slightly."""
        import random
        random.seed(42)
        a = _next_backoff(1)
        random.seed(99)
        b = _next_backoff(1)
        assert a != b


class TestEnqueue:
    def test_basic_enqueue(self, app_fixture):
        with app_fixture.app_context():
            jid = enqueue("test_ok", {"key": "val"})
            job = db_session_get(int(jid))
            assert job is not None
            assert job.status == "pending"
            assert job.job_type == "test_ok"

    def test_unknown_type_raises(self, app_fixture):
        with app_fixture.app_context():
            with pytest.raises(ValueError, match="Unknown job type"):
                enqueue("nonexistent", {})

    def test_dedup_skips_duplicate(self, app_fixture):
        with app_fixture.app_context():
            jid1 = enqueue("test_ok", {}, dedup_key="dup-1")
            jid2 = enqueue("test_ok", {}, dedup_key="dup-1")
            assert jid1 == jid2

    def test_custom_max_retries(self, app_fixture):
        with app_fixture.app_context():
            jid = enqueue("test_ok", {}, max_retries=10)
            job = db_session_get(int(jid))
            assert job.max_retries == 10


def db_session_get(job_id: int):
    from app.extensions import db
    return db.session.get(JobAttempt, job_id)


class TestProcessPending:
    def test_success(self, app_fixture):
        with app_fixture.app_context():
            jid = enqueue("test_ok", {"calls": []})
            count = process_pending(clock=_freeze_clock(datetime.now(timezone.utc)))
            assert count == 1
            job = db_session_get(int(jid))
            assert job.status == "completed"
            assert job.attempts == 1

    def test_retry_then_success(self, app_fixture):
        """A flaky job should eventually succeed."""
        handler = _FlakyHandler(fail_times=2)
        _REGISTRY["test_flaky"] = handler

        with app_fixture.app_context():
            jid = enqueue("test_flaky", {})

            # Attempt 1: fail
            now = datetime.now(timezone.utc)
            process_pending(clock=_freeze_clock(now))
            job = db_session_get(int(jid))
            assert job.status == "retry"
            assert job.attempts == 1

            # Advance past backoff
            later = now + timedelta(seconds=60)
            process_pending(clock=_freeze_clock(later))
            job = db_session_get(int(jid))
            assert job.status == "retry"
            assert job.attempts == 2

            # Attempt 3: succeed
            even_later = later + timedelta(seconds=60)
            process_pending(clock=_freeze_clock(even_later))
            job = db_session_get(int(jid))
            assert job.status == "completed"
            assert job.attempts == 3
            assert handler.call_count == 3

    def test_moves_to_dlq_after_max_retries(self, app_fixture):
        with app_fixture.app_context():
            jid = enqueue("test_fail", {}, max_retries=3)
            now = datetime.now(timezone.utc)

            for i in range(5):  # more than enough
                process_pending(clock=_freeze_clock(now + timedelta(seconds=i * 300)))

            job = db_session_get(int(jid))
            assert job.status == "dead"
            assert job.attempts >= job.max_retries

            # Verify DLQ entry exists
            from app.extensions import db
            from sqlalchemy import func
            dlq_count = db.session.query(func.count(DeadLetter.id)).scalar()
            assert dlq_count >= 1


class TestJobHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/jobs/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert "stats" in data

    def test_health_degraded_when_dlq(self, app_fixture, client):
        with app_fixture.app_context():
            enqueue("test_fail", {}, max_retries=1)
            now = datetime.now(timezone.utc)
            for i in range(3):
                process_pending(clock=_freeze_clock(now + timedelta(seconds=i * 300)))

        resp = client.get("/jobs/health")
        data = resp.get_json()
        assert data["status"] == "degraded"
        assert data["stats"].get("dead", 0) > 0


class TestJobAdminEndpoints:
    def test_list_jobs_forbidden_for_user(self, client, auth_header):
        resp = client.get("/jobs", headers=auth_header)
        assert resp.status_code == 403

    def test_dlq_retry(self, app_fixture, client, auth_header):
        # Make user admin
        from app.extensions import db
        with app_fixture.app_context():
            user = db.session.query(User).first()
            user.role = "ADMIN"
            db.session.commit()

        # Create a DLQ entry
        with app_fixture.app_context():
            enqueue("test_fail", {}, max_retries=1)
            now = datetime.now(timezone.utc)
            for i in range(3):
                process_pending(clock=_freeze_clock(now + timedelta(seconds=i * 300)))

        admin_header = auth_header
        resp = client.get("/jobs/dlq", headers=admin_header)
        assert resp.status_code == 200
        items = resp.get_json()["items"]
        assert len(items) >= 1

        # Retry first DLQ entry
        dlq_id = items[0]["id"]
        resp = client.post(f"/jobs/dlq/{dlq_id}/retry", headers=admin_header)
        assert resp.status_code == 200
        assert "new_job_id" in resp.get_json()

    def test_process_endpoint(self, app_fixture, client, auth_header):
        from app.extensions import db
        with app_fixture.app_context():
            user = db.session.query(User).first()
            user.role = "ADMIN"
            db.session.commit()

        resp = client.post("/jobs/process", headers=auth_header)
        assert resp.status_code == 200
        assert "processed" in resp.get_json()


class TestMetricsIntegration:
    def test_job_metrics_exposed(self, app_fixture, client, auth_header):
        """After processing jobs, /metrics should contain job counters."""
        from app.extensions import db
        with app_fixture.app_context():
            user = db.session.query(User).first()
            user.role = "ADMIN"
            db.session.commit()
            enqueue("test_ok", {"calls": []})
            process_pending(clock=_freeze_clock(datetime.now(timezone.utc)))

        resp = client.get("/metrics")
        assert resp.status_code == 200
        payload = resp.get_data(as_text=True)
        assert "finmind_job_events_total" in payload
        assert 'event="completed"' in payload
