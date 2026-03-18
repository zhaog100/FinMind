"""Tests for job_manager and monitoring services."""

from __future__ import annotations

import time
import pytest

from app.services.job_manager import JobManager, JobStatus, _backoff_seconds


class FakeRedis:
    """In-memory dict-based Redis mock for unit tests."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value: str):
        self._store[key] = value

    def delete(self, key: str):
        self._store.pop(key, None)

    def sadd(self, key: str, *values: str):
        self._sets.setdefault(key, set()).update(values)

    def srem(self, key: str, *values: str):
        s = self._sets.get(key, set())
        for v in values:
            s.discard(v)

    def smembers(self, key: str) -> set[str]:
        return self._sets.get(key, set())

    def scan_iter(self, pattern: str):
        prefix = pattern.replace("*", "")
        for key in list(self._store.keys()):
            if key.startswith(prefix):
                yield key


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def manager(fake_redis):
    return JobManager(redis_conn=fake_redis)


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Speed up retries for all tests."""
    import app.services.job_manager as jm
    monkeypatch.setattr(jm, "_backoff_seconds", lambda r: 0.01)


class TestJobManager:

    def test_submit_success(self, manager):
        job = manager.submit(lambda: "ok", name="test_ok")
        time.sleep(0.3)
        result = manager.get(job.id)
        assert result is not None
        assert result.status.value == "success"
        assert result.retries == 0

    def test_submit_retry_then_success(self, manager):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return "recovered"

        job = manager.submit(flaky, name="flaky", max_retries=5)
        time.sleep(0.5)
        result = manager.get(job.id)
        assert result.status.value == "success"
        assert result.retries == 2

    def test_submit_permanent_failure_goes_to_dlq(self, manager, fake_redis):
        def always_fails():
            raise RuntimeError("permanent")

        job = manager.submit(always_fails, name="failer", max_retries=3)
        time.sleep(0.5)
        result = manager.get(job.id)
        assert result.status.value == "failed"
        assert result.retries == 3
        assert job.id in fake_redis.smembers("finmind:jobs:dlq")

    def test_get_nonexistent(self, manager):
        assert manager.get("nonexistent") is None

    def test_list_all(self, manager):
        jobs = [manager.submit(lambda: i, name=f"job_{i}") for i in range(3)]
        time.sleep(0.3)
        ids = {j.id for j in manager.list_all()}
        for j in jobs:
            assert j.id in ids

    def test_stats(self, manager):
        manager.submit(lambda: "ok", name="s1")
        manager.submit(lambda: "ok", name="s2")
        time.sleep(0.3)
        stats = manager.stats()
        assert stats["total"] >= 2
        assert stats["success"] >= 2

    def test_retry_resets_failed_job(self, manager, fake_redis):
        def fail():
            raise RuntimeError("nope")

        job = manager.submit(fail, name="willfail", max_retries=1)
        time.sleep(0.3)
        assert manager.get(job.id).status.value == "failed"
        assert job.id in fake_redis.smembers("finmind:jobs:dlq")

        retried = manager.retry(job.id)
        assert retried.status.value == "retrying"
        assert retried.retries == 0
        assert job.id not in fake_redis.smembers("finmind:jobs:dlq")

    def test_retry_nonexistent_returns_none(self, manager):
        assert manager.retry("nonexistent") is None

    def test_purge_dead_letter(self, manager, fake_redis):
        def fail():
            raise RuntimeError("nope")

        job = manager.submit(fail, name="willfail", max_retries=1)
        time.sleep(0.3)
        assert job.id in fake_redis.smembers("finmind:jobs:dlq")

        purged = manager.purge_dead_letter()
        assert purged >= 1
        assert manager.get(job.id) is None

    def test_backoff_values(self):
        assert _backoff_seconds(0) == 2.0
        assert _backoff_seconds(1) == 4.0
        assert _backoff_seconds(2) == 8.0
        assert _backoff_seconds(3) == 16.0
        assert _backoff_seconds(4) == 32.0


class TestJobMonitor:

    def test_metrics_basic(self, manager):
        from app.services.monitoring import JobMonitor
        monitor = JobMonitor(manager)
        manager.submit(lambda: "ok", name="m1")
        time.sleep(0.2)
        m = monitor.get_metrics()
        assert m.total_submitted >= 1
        assert m.success_rate >= 0.0
        d = monitor.export_dict()
        assert "total_submitted" in d
        assert "success_rate" in d

    def test_export_json(self, manager):
        from app.services.monitoring import JobMonitor
        monitor = JobMonitor(manager)
        j = monitor.export_json()
        import json
        data = json.loads(j)
        assert "total_submitted" in data
