from datetime import UTC, datetime, timedelta

from ai_ops_center import connectivity
from ai_ops_center.ops2 import _freshen_machine_statuses


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, *_args):
        return None

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def cursor(self):
        return _Cursor(self.rows)


def test_connection_snapshot_ages_online_reports(monkeypatch):
    now = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
    rows = [
        {"status": "online", "last_checked_at": now - timedelta(seconds=100), "updated_at": now},
        {"status": "offline", "last_checked_at": now - timedelta(seconds=10), "updated_at": now},
    ]
    monkeypatch.setattr(connectivity, "connect", lambda local=False: _Connection(rows))

    snapshot = connectivity.connection_snapshot(stale_after_seconds=90, now=now)

    assert snapshot[0]["reported_status"] == "online"
    assert snapshot[0]["status"] == "stale"
    assert snapshot[0]["is_online"] is False
    assert snapshot[1]["status"] == "offline"


def test_machine_freshness_counts_active_and_employed_laptops():
    now = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
    machines = [
        {"machine_id": "brain", "role": "brain", "status": "online", "last_seen_at": now, "active_agent_count": 2},
        {"machine_id": "dev", "role": "development", "status": "online", "last_seen_at": now, "active_agent_count": 3},
        {"machine_id": "research", "role": "research", "status": "online", "last_seen_at": now - timedelta(minutes=3), "active_agent_count": 1},
        {"machine_id": "business", "role": "business", "status": None, "last_seen_at": None, "active_agent_count": 0},
    ]

    workforce = {"dev": "employed", "research": "employed", "business": "employed"}
    freshened, summary = _freshen_machine_statuses(machines, 90, now, workforce)

    assert [row["status"] for row in freshened[1:]] == ["online", "stale", "never_seen"]
    assert summary == {
        "registered_laptops": 3,
        "active_laptops": 1,
        "employed_laptops": 3,
        "stale_laptops": 1,
        "never_seen_laptops": 1,
        "stale_after_seconds": 90,
    }
