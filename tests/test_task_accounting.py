import asyncio
import json
from datetime import UTC, datetime

from ai_ops_center import api
from ai_ops_center.tasks import _build_task_summary, task_accounting_audit


def test_lifetime_completed_total_equals_per_machine_sum():
    generated_at = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
    rows = [
        {"machine_id": "dev-laptop", "status": "completed", "count": 87},
        {"machine_id": "dev-laptop", "status": "running", "count": 2},
        {"machine_id": "research-laptop", "status": "completed", "count": 64},
        {"machine_id": "business-laptop", "status": "queued", "count": 5},
        {"machine_id": None, "status": "completed", "count": 3},
    ]

    summary = _build_task_summary(rows, generated_at=generated_at)

    assert summary["completed_total"] == 154
    assert summary["total"] == 161
    assert summary["by_machine"]["dev-laptop"]["completed"] == 87
    assert summary["by_machine"]["unassigned"]["completed"] == 3
    assert summary["contract"]["scope"] == "lifetime"
    assert summary["contract"]["recent_list_independent"] is True
    assert all(summary["contract"]["invariants"].values())
    audit = task_accounting_audit(summary, recent_returned=50, readiness_summary=summary)
    assert audit["status"] == "passed"
    assert all(audit["rubric"].values())


def test_lifetime_summary_is_not_derived_from_recent_list_limit():
    rows = [{"machine_id": "dev-laptop", "status": "completed", "count": 500}]

    summary = _build_task_summary(rows)

    assert summary["completed_total"] == 500
    assert summary["completed_total"] > 50


def test_sse_carries_lifetime_summary_beside_limited_rows(monkeypatch):
    lifetime = _build_task_summary(
        [{"machine_id": "dev-laptop", "status": "completed", "count": 999}]
    )
    recent = [{"id": index, "status": "completed"} for index in range(50)]
    monkeypatch.setattr(api, "task_snapshot", lambda: recent)
    monkeypatch.setattr(api, "task_summary", lambda: lifetime)
    monkeypatch.setattr(api, "readiness_snapshot", lambda: {"task_summary": lifetime})
    monkeypatch.setattr(api, "connection_snapshot", lambda: [])
    monkeypatch.setattr(api, "factory_snapshot", lambda: {})
    monkeypatch.setattr(api, "approval_snapshot", lambda limit=20: [])
    monkeypatch.setattr(api, "listener_snapshot", lambda limit=20: [])
    monkeypatch.setattr(api, "speaker_feed", lambda machine_id: {})
    monkeypatch.setattr(api, "collaboration_snapshot", lambda limit=20: {"peer_requests": []})
    monkeypatch.setattr(api, "integration_status", lambda: {})
    monkeypatch.setattr(api, "model_solution_snapshot", lambda limit=10: [])
    monkeypatch.setattr(api, "queue_health", lambda: {"queued": 0, "running": 0, "stalled_running": 0})

    async def read_one_event():
        response = await api.stream()
        iterator = response.body_iterator
        event = await iterator.__anext__()
        await iterator.aclose()
        return json.loads(event.removeprefix("data: ").strip())

    payload = asyncio.run(read_one_event())

    assert len(payload["tasks"]) == 50
    assert payload["task_summary"]["completed_total"] == 999
    assert payload["task_list"]["scope"] == "recent_prioritized"
    assert payload["task_summary"]["contract"]["scope"] == "lifetime"
    assert payload["task_accounting_audit"]["status"] == "passed"
    assert all(payload["connection_summary"]["contract"]["invariants"].values())
    assert payload["collaboration"]["peer_requests"] == []
