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

    monkeypatch.setattr(worker, "apply_migrations", lambda *args, **kwargs: {})
    monkeypatch.setattr(worker, "record_heartbeat", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "_consume_machine_messages", lambda *args, **kwargs: 0)
    monkeypatch.setattr(worker, "steward_queue", lambda *args, **kwargs: {})
    monkeypatch.setattr(worker, "claim_next_task", lambda *args, **kwargs: next(claims))
    monkeypatch.setattr(worker, "complete_task", lambda *args, **kwargs: True)
    monkeypatch.setattr(worker, "_execute_with_lease_heartbeats", lambda *args, **kwargs: "done")
    monkeypatch.setattr(worker, "_report_task_completion", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "_respond_to_linked_peer_request", lambda *args, **kwargs: None)

    class StopWorker(Exception):
        pass

    def stop_on_idle_sleep(seconds):
        sleeps.append(seconds)
        raise StopWorker

    monkeypatch.setattr(worker.time, "sleep", stop_on_idle_sleep)

    with pytest.raises(StopWorker):
        worker.run_worker("business-laptop", sleep_seconds=9, work_seconds=0)

    assert sleeps == [9]


def test_worker_acknowledges_direct_machine_messages_only(monkeypatch):
    messages = [
        {"id": 1, "target_id": "business-laptop", "subject": "Pulse", "priority": 90, "status": "delivered"},
        {"id": 2, "target_id": "all", "subject": "Broadcast", "priority": 50, "status": "delivered"},
    ]
    events = []
    acknowledgements = []
    monkeypatch.setattr(worker, "speaker_feed", lambda *_args, **_kwargs: {"messages": messages})
    monkeypatch.setattr(worker, "submit_listener_event", lambda **kwargs: events.append(kwargs))
    monkeypatch.setattr(worker, "acknowledge_speaker_message", lambda message_id, actor, **_kwargs: acknowledgements.append((message_id, actor)))

    assert worker._consume_machine_messages("business-laptop") == 1
    assert acknowledgements == [(1, "business-laptop")]
    assert events[0]["metadata"]["speaker_message_id"] == 1


def test_connectivity_probe_is_real_machine_evidence():
    result = worker._execute_task(
        "business-laptop",
        {"id": 42, "metadata": {"executor": "connectivity_probe"}},
    )

    assert '"machine_id": "business-laptop"' in result
    assert '"executor": "connectivity_probe"' in result
