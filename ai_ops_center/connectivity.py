from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .db import connect


def record_connection(
    source_machine_id: str,
    target_machine_id: str,
    channel: str,
    status: str,
    latency_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into machine_connections (
                    source_machine_id, target_machine_id, channel, status,
                    latency_ms, last_checked_at, metadata, updated_at
                )
                values (%s, %s, %s, %s, %s, now(), %s::jsonb, now())
                on conflict (source_machine_id, target_machine_id, channel) do update set
                    status = excluded.status,
                    latency_ms = excluded.latency_ms,
                    last_checked_at = excluded.last_checked_at,
                    metadata = excluded.metadata,
                    updated_at = now()
                """,
                (
                    source_machine_id,
                    target_machine_id,
                    channel,
                    status,
                    latency_ms,
                    _json_metadata(metadata),
                ),
            )
        conn.commit()


DEFAULT_STALE_AFTER_SECONDS = 90
ONLINE_STATUSES = {"online", "connected", "healthy", "ok", "reachable", "ready"}


def connection_snapshot(
    local: bool = False,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return connections with freshness-aware effective status.

    Agents report a point-in-time status.  Without aging that report, a laptop
    which disappeared from the network continued to look online forever.
    ``reported_status`` retains the agent value while ``status`` is the value
    consumers should use for current dashboards and routing.
    """
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be at least 1")
    observed_at = now or datetime.now(UTC)
    cutoff = observed_at - timedelta(seconds=stale_after_seconds)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    source_machine_id, target_machine_id, channel, status,
                    latency_ms, last_checked_at, metadata, updated_at
                from machine_connections
                order by target_machine_id, channel
                """
            )
            rows = [dict(row) for row in cur.fetchall()]

    for row in rows:
        reported_status = str(row.get("status") or "unknown").strip().lower()
        checked_at = row.get("last_checked_at") or row.get("updated_at")
        is_stale = checked_at is None or checked_at < cutoff
        row["reported_status"] = reported_status
        row["is_stale"] = is_stale
        row["age_seconds"] = max(0.0, (observed_at - checked_at).total_seconds()) if checked_at else None
        row["status"] = "stale" if is_stale and reported_status in ONLINE_STATUSES else reported_status
        row["is_online"] = row["status"] in ONLINE_STATUSES
    return rows


def connection_summary(connections: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize effective connectivity without treating stale reports as live."""
    online = [row for row in connections if row.get("is_online")]
    stale = [row for row in connections if row.get("is_stale")]
    targets_online = {str(row["target_machine_id"]) for row in online if row.get("target_machine_id")}
    targets_reported = {str(row["target_machine_id"]) for row in connections if row.get("target_machine_id")}
    availability_checks = {
        "at_least_one_online_record": len(online) > 0,
        "at_least_one_online_target": len(targets_online) > 0,
    }
    return {
        "records": len(connections),
        "online_records": len(online),
        "stale_records": len(stale),
        "reported_targets": len(targets_reported),
        "online_targets": len(targets_online),
        "availability": {
            "status": "passed" if all(availability_checks.values()) else "failed",
            "rubric": availability_checks,
        },
        "contract": {
            "version": 1,
            "freshness_aware": True,
            "effective_status_field": "status",
            "raw_status_field": "reported_status",
            "invariants": {
                "online_records_are_fresh": all(not bool(row.get("is_stale")) for row in online),
                "stale_online_reports_are_not_effectively_online": all(
                    not bool(row.get("is_online"))
                    for row in stale
                    if row.get("reported_status") in ONLINE_STATUSES
                ),
            },
        },
    }


def _json_metadata(metadata: dict[str, Any] | None) -> str:
    import json

    return json.dumps(metadata or {})
