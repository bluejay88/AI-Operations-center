from datetime import UTC, datetime, timedelta

from ai_ops_center import connectivity, ops2
from ai_ops_center.connectivity import connection_summary
from ai_ops_center.ops2 import _freshen_machine_statuses, _is_dashboard_presence


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


class _TelemetryCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement, *_args):
        self.statements.append(statement)

    def fetchone(self):
        return {"id": 1, "machine_id": "dev-laptop"}


class _TelemetryConnection:
    def __init__(self):
        self.telemetry_cursor = _TelemetryCursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def cursor(self):
        return self.telemetry_cursor

    def commit(self):
        self.committed = True


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
    summary = connection_summary(snapshot)
    assert summary["online_records"] == 0
    assert all(summary["contract"]["invariants"].values())
    assert summary["availability"]["status"] == "failed"
    assert not any(summary["availability"]["rubric"].values())


def test_connection_availability_requires_a_fresh_online_target():
    now = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)
    connections = [
        {
            "source_machine_id": "brain",
            "target_machine_id": "dev",
            "channel": "ssh-22",
            "status": "online",
            "last_checked_at": now,
            "updated_at": now,
        },
        {
            "source_machine_id": "brain",
            "target_machine_id": "dev",
            "channel": "tailscale-ping",
            "status": "online",
            "last_checked_at": now,
            "updated_at": now,
        },
    ]

    for row in connections:
        row["reported_status"] = row["status"]
        row["is_stale"] = False
        row["is_online"] = True

    summary = connection_summary(connections)

    assert summary["online_records"] == 2
    assert summary["online_targets"] == 1
    assert summary["availability"]["status"] == "passed"
    assert all(summary["availability"]["rubric"].values())


def test_dashboard_presence_is_not_worker_telemetry():
    assert _is_dashboard_presence({"metadata": {"source": "browser-dashboard"}}) is True
    assert _is_dashboard_presence({"metadata": {"source": "worker-agent"}}) is False
    assert _is_dashboard_presence({}) is False


def test_dashboard_presence_does_not_refresh_authoritative_machine_status(monkeypatch):
    connection = _TelemetryConnection()
    monkeypatch.setattr(ops2, "connect", lambda local=False: connection)

    result = ops2.publish_device_telemetry({
        "machine_id": "dev-laptop",
        "device_name": "Node Console",
        "metadata": {"source": "browser-dashboard", "observation_kind": "dashboard_presence"},
    })

    sql = "\n".join(connection.telemetry_cursor.statements).lower()
    assert "insert into device_telemetry" in sql
    assert "machine_status_current" not in sql
    assert "machine_heartbeats" not in sql
    assert connection.committed is True
    assert result["telemetry"]["machine_id"] == "dev-laptop"


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
    assert summary["registered_laptops"] == 3
    assert summary["connected_laptops"] == 1
    assert summary["active_laptops"] == 1
    assert summary["employed_laptops"] == 3
    assert summary["stale_laptops"] == 1
    assert summary["never_seen_laptops"] == 1
    assert all(summary["contract"]["invariants"].values())
