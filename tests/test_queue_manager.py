import pytest

from ai_ops_center import worker
from ai_ops_center.migrations import _checksum_matches
from ai_ops_center.queue_manager import (
    rank_fallback_targets,
    retry_delay_seconds,
    select_fallback_target,
    should_reroute_task,
    task_is_automatic_eligible,
    task_is_claim_eligible,
)


def test_retry_delay_is_exponential_and_bounded():
    assert [retry_delay_seconds(value) for value in (0, 1, 2, 3)] == [5, 5, 10, 20]
    assert retry_delay_seconds(100) == 300


def test_migration_checksum_compatibility_is_narrowly_scoped():
    historical = "829a0d27a5f2f03b9b27d54bab911a720b2aff555e659e5713480262431a69ad"
    current = "1457c0aaeb6836c565f4af1d2945eccb876836bfa9a55e3b6856ef489f1e6fe6"
    assert _checksum_matches("002", historical, current) is True
    assert _checksum_matches("002", "unexpected", current) is False
    assert _checksum_matches("999", historical, current) is False


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


def test_machine_bound_work_can_be_claimed_but_not_automatically_rerouted():
    metadata = {"no_failover": True, "pinned_machine": "business-laptop", "requires_local_resources": True}
    assert task_is_claim_eligible(metadata) is True
    assert task_is_automatic_eligible(metadata) is False


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


def test_fallback_selection_skips_idle_full_target_for_spare_capacity():
    loads = {
        "source": {"running": 0, "queued": 1, "capacity": 2},
        "idle-full": {"running": 0, "queued": 1, "capacity": 1},
        "busy-spare": {"running": 1, "queued": 0, "capacity": 3},
    }

    assert select_fallback_target(loads, "source", source_unhealthy=False) == "busy-spare"


def test_starved_portable_work_moves_to_a_target_with_capacity():
    assert should_reroute_task(
        source_unhealthy=False,
        source_running=0,
        assignment_generation=0,
        target_has_room=True,
        balances_backlog=False,
        seconds_since_assignment=60,
    ) is True


def test_recent_balanced_work_stays_on_its_assigned_healthy_machine():
    assert should_reroute_task(
        source_unhealthy=False,
        source_running=0,
        assignment_generation=0,
        target_has_room=True,
        balances_backlog=False,
        seconds_since_assignment=59,
    ) is False


def test_starvation_fallback_is_bounded_against_ping_pong():
    assert should_reroute_task(
        source_unhealthy=False,
        source_running=0,
        assignment_generation=2,
        target_has_room=True,
        balances_backlog=False,
        seconds_since_assignment=600,
    ) is False


def test_starvation_fallback_does_not_move_work_from_an_active_source():
    assert should_reroute_task(
        source_unhealthy=False,
        source_running=1,
        assignment_generation=0,
        target_has_room=True,
        balances_backlog=False,
        seconds_since_assignment=600,
    ) is False


def test_starvation_fallback_requires_target_capacity():
    assert should_reroute_task(
        source_unhealthy=False,
        source_running=0,
        assignment_generation=0,
        target_has_room=False,
        balances_backlog=False,
        seconds_since_assignment=600,
    ) is False


def test_unhealthy_source_moves_even_before_starvation_threshold():
    assert should_reroute_task(
        source_unhealthy=True,
        source_running=0,
        assignment_generation=9,
        target_has_room=False,
        balances_backlog=False,
        seconds_since_assignment=0,
    ) is True


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


def test_speaker_receipt_does_not_echo_to_speaker(monkeypatch):
    from contextlib import contextmanager

    from ai_ops_center import brain_bus

    class Cursor:
        def __init__(self):
            self.last_sql = ""

        def execute(self, sql, _params=()):
            self.last_sql = sql

        def fetchone(self):
            if "select * from listener_events" in self.last_sql:
                return {
                    "id": 1,
                    "source_id": "business-laptop",
                    "event_type": "speaker_message_received",
                    "subject": "Received: diagnostic",
                    "body": "received",
                    "priority": 90,
                    "metadata": {"speaker_message_id": 77, "machine_id": "business-laptop"},
                }
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            return None

    @contextmanager
    def fake_connect(**_kwargs):
        yield Connection()

    monkeypatch.setattr(brain_bus, "connect", fake_connect)
    monkeypatch.setattr(brain_bus, "create_speaker_message", lambda **_kwargs: pytest.fail("receipt echoed to speaker"))

    assert brain_bus.apply_brain_logic(1) == [
        {"type": "speaker_receipt_recorded", "message_id": 77, "machine_id": "business-laptop"}
    ]
