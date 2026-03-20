"""Tests for background job retry service."""
import time
import pytest
from app.services.job_retry import (
    RetryPolicy, submit_job, execute_job, get_job, list_jobs,
    get_dead_letter_queue, retry_dead_job, get_metrics, purge_jobs,
    register_policy, _jobs,
)


def _reset():
    _jobs.clear()


def test_successful_job():
    _reset()
    jid = submit_job(lambda: "ok", description="test")
    result = execute_job(jid)
    assert result["status"] == "success"
    assert result["attempt"] == 1


def test_job_retry_then_success():
    _reset()
    call_count = 0
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("not yet")
        return "done"
    jid = submit_job(flaky, policy_name="aggressive")
    register_policy("aggressive", RetryPolicy(max_retries=5, base_delay=0.05, max_delay=0.1))
    result = execute_job(jid)
    assert result["status"] == "success"
    assert result["attempt"] == 3


def test_job_exhausts_retries():
    _reset()
    def always_fail():
        raise RuntimeError("nope")
    jid = submit_job(always_fail, description="fail test")
    register_policy("tight", RetryPolicy(max_retries=2, base_delay=0.01, max_delay=0.05))
    # Re-submit with tight policy
    _jobs[jid]["policy_name"] = "tight"
    _jobs[jid]["max_retries"] = 2
    result = execute_job(jid)
    assert result["status"] == "dead"
    assert result["attempt"] == 2


def test_list_jobs_filters():
    _reset()
    submit_job(lambda: 1, queue="email", description="e1")
    submit_job(lambda: 2, queue="email", description="e2")
    submit_job(lambda: 3, queue="sms", description="s1")
    email_jobs = list_jobs(queue="email")
    assert len(email_jobs) == 2
    all_jobs = list_jobs()
    assert len(all_jobs) == 3


def test_dead_letter_queue():
    _reset()
    submit_job(lambda: exec("raise Exception"), queue="dlq", description="dead")
    execute_job(list(_jobs.keys())[-1])
    dlq = get_dead_letter_queue()
    assert len(dlq) == 1


def test_retry_dead_job():
    _reset()
    def flaky():
        if not getattr(flaky, '_called', False):
            flaky._called = True
            raise ValueError("first fail")
        return "recovered"
    jid = submit_job(flaky, description="retry-test")
    register_policy("rtest", RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.05))
    _jobs[jid]["policy_name"] = "rtest"
    _jobs[jid]["max_retries"] = 1
    execute_job(jid)
    assert get_job(jid)["status"] == "dead"
    result = retry_dead_job(jid)
    assert result["status"] == "success"


def test_metrics():
    _reset()
    submit_job(lambda: "ok")
    submit_job(lambda: exec("raise Exception"))
    execute_job(list(_jobs.keys())[0])
    execute_job(list(_jobs.keys())[1])
    m = get_metrics()
    assert m["total_submitted"] == 2
    assert m["total_success"] == 1


def test_purge():
    _reset()
    submit_job(lambda: "ok")
    jid = list(_jobs.keys())[0]
    execute_job(jid)
    removed = purge_jobs(older_than_hours=0)
    assert removed == 1
    assert get_job(jid) is None
