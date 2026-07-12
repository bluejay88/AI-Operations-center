from __future__ import annotations

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


def connection_snapshot(local: bool = False) -> list[dict[str, Any]]:
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
            return [dict(row) for row in cur.fetchall()]


def _json_metadata(metadata: dict[str, Any] | None) -> str:
    import json

    return json.dumps(metadata or {})
