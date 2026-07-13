import pytest

from ai_ops_center import worker
from ai_ops_center.queue_manager import rank_fallback_targets, retry_delay_seconds, task_is_automatic_eligible


def test_retry_delay_is_exponential_and_bounded():
    assert [retry_delay_seconds(value) for value in (0, 1, 2, 3)] == [5, 5, 10, 20]
    assert retry_delay_seconds(100) == 300


@pytest.mark.parametrize(
    "metadata",
    [
        {"queue_state": "pending_approval"},
        {"requires_approval": True},
        {"requires_approval": "yes", "approval_status": "pending"},
        {"no_failover": True},
        {"pinned_machine": "dev-laptop"},
        {"requires_local_resources": True},
    ],
)
def test_approval_and_machine_bound_tasks_are_held(metadata):
    assert task_is_automatic_eligible(metadata) is False


def test_approved_and_portable_tasks_are_eligible():
    assert task_is_automatic_eligible({}) is True
    assert task_is_automatic_eligible({"requires_approval": True, "approval_status": "approved"}) is True


def test_fallback_ranking_excludes_source_and_prefers_idle_normalized_capacity():
    loads = {
        "source": {"running": 0, "queued": 20, "capacity": 4},
        "busy": {"running": 1, "queued": 0, "capacity": 4},
        "idle-small": {"running": 0, "queued": 1, "capacity": 2},
        "idle-large": {"running": 0, "queued": 1, "capacity": 4},
    }

    ranked = rank_fallback_targets(loads, "source")

    assert ranked == ["idle-large", "idle-small", "busy"]
    assert "source" not in ranked


def test_worker_immediately_requests_more_work_after_completion(monkeypatch):
    claims = iter([{"id": 7, "claim_token": "token", "title": "task"}, None])
    sleeps = []

    monkeypatch.setattr(worker, "record_heartbeat", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "steward_queue", lambda *args, **kwargs: {})
    monkeypatch.setattr(worker, "claim_next_task", lambda *args, **kwargs: next(claims))
    monkeypatch.setattr(worker, "complete_task", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker, "_simulate_agent_work", lambda task: "done")

    class StopWorker(Exception):
        pass

    def stop_on_idle_sleep(seconds):
        sleeps.append(seconds)
        raise StopWorker

    monkeypatch.setattr(worker.time, "sleep", stop_on_idle_sleep)

    with pytest.raises(StopWorker):
        worker.run_worker("business-laptop", sleep_seconds=9, work_seconds=0)

    assert sleeps == [9]
