from __future__ import annotations

import json
from typing import Any

from .db import connect


VALID_DECISIONS = {"approved", "rejected", "needs_changes", "deployed"}


def create_approval_request(
    title: str,
    request_type: str,
    requester_machine_id: str,
    requester_agent_id: str,
    summary: str,
    proposed_changes: str,
    risk_level: str = "medium",
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into approval_requests (
                    title, request_type, requester_machine_id, requester_agent_id,
                    risk_level, summary, proposed_changes, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning id
                """,
                (
                    title,
                    request_type,
                    requester_machine_id,
                    requester_agent_id,
                    risk_level,
                    summary,
                    proposed_changes,
                    json.dumps(metadata or {}),
                ),
            )
            request_id = int(cur.fetchone()["id"])
            _insert_event(cur, request_id, "submitted", requester_agent_id, "Approval request submitted.", metadata or {})
        conn.commit()
    return request_id


def approval_snapshot(limit: int = 50, local: bool = False) -> list[dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, title, request_type, requester_machine_id, requester_agent_id,
                    risk_level, status, summary, proposed_changes, audit_feedback,
                    created_at, reviewed_at, approved_at, deployed_at, updated_at
                from approval_requests
                order by
                    case status
                        when 'pending' then 0
                        when 'needs_changes' then 1
                        when 'approved' then 2
                        when 'deployed' then 3
                        else 4
                    end,
                    created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def approval_detail(request_id: int, local: bool = False) -> dict[str, Any] | None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from approval_requests where id = %s", (request_id,))
            request = cur.fetchone()
            if not request:
                return None
            cur.execute(
                """
                select event_type, actor, message, metadata, created_at
                from approval_events
                where approval_request_id = %s
                order by created_at
                """,
                (request_id,),
            )
            events = [dict(row) for row in cur.fetchall()]
    detail = dict(request)
    detail["events"] = events
    return detail


def review_approval_request(
    request_id: int,
    decision: str,
    feedback: str,
    actor: str = "brain-gaming-pc",
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")

    timestamp_field = {
        "approved": "approved_at = now(), reviewed_at = coalesce(reviewed_at, now()),",
        "rejected": "reviewed_at = now(),",
        "needs_changes": "reviewed_at = now(),",
        "deployed": "deployed_at = now(),",
    }[decision]
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                update approval_requests
                set status = %s,
                    audit_feedback = %s,
                    {timestamp_field}
                    updated_at = now()
                where id = %s
                returning *
                """,
                (decision, feedback, request_id),
            )
            request = cur.fetchone()
            if not request:
                raise ValueError(f"approval request {request_id} not found")
            _insert_event(cur, request_id, decision, actor, feedback, metadata or {})
        conn.commit()
    return dict(request)


def _insert_event(cur: Any, request_id: int, event_type: str, actor: str, message: str, metadata: dict[str, Any]) -> None:
    cur.execute(
        """
        insert into approval_events (approval_request_id, event_type, actor, message, metadata)
        values (%s, %s, %s, %s, %s::jsonb)
        """,
        (request_id, event_type, actor, message, json.dumps(metadata)),
    )

