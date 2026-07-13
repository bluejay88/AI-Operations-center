from __future__ import annotations

import json
from typing import Any

from .approvals import create_approval_request
from .db import connect
from .phoenix import laptop_instruction, phoenix_briefing
from .tasks import create_manual_task


def submit_listener_event(
    source_type: str,
    source_id: str,
    event_type: str,
    subject: str,
    body: str,
    priority: int = 50,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    metadata = metadata or {}
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into listener_events (source_type, source_id, event_type, subject, body, priority, metadata)
                values (%s, %s, %s, %s, %s, %s, %s::jsonb)
                returning id
                """,
                (source_type, source_id, event_type, subject, body, priority, json.dumps(metadata, default=str)),
            )
            event_id = int(cur.fetchone()["id"])
        conn.commit()

    actions = apply_brain_logic(event_id, local=local)
    return {"event_id": event_id, "actions": actions}


def listener_snapshot(limit: int = 50, local: bool = False) -> list[dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, source_type, source_id, event_type, subject, body, priority, metadata, created_at, processed_at
                from listener_events
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def speaker_feed(target_id: str, include_acknowledged: bool = False, local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            status_filter = "" if include_acknowledged else "and status != 'acknowledged'"
            cur.execute(
                f"""
                select id, target_type, target_id, message_type, subject, body, priority,
                    status, metadata, created_at, delivered_at, acknowledged_at
                from speaker_messages
                where target_id in (%s, 'all')
                {status_filter}
                order by priority desc, created_at desc
                limit 50
                """,
                (target_id,),
            )
            messages = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                update speaker_messages
                set status = case when status = 'pending' then 'delivered' else status end,
                    delivered_at = coalesce(delivered_at, now())
                where target_id in (%s, 'all')
                  and status = 'pending'
                """,
                (target_id,),
            )
        conn.commit()

    instructions = ""
    if target_id in {"brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop"}:
        instructions = laptop_instruction(target_id)
    return {
        "target_id": target_id,
        "messages": messages,
        "instructions": instructions,
        "phoenix_briefing": phoenix_briefing(local=local) if target_id == "brain-gaming-pc" else "",
    }


def acknowledge_speaker_message(message_id: int, actor: str, local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update speaker_messages
                set status = 'acknowledged',
                    acknowledged_at = now(),
                    metadata = metadata || jsonb_build_object('acknowledged_by', %s::text)
                where id = %s
                  and target_id = %s
                returning id, target_id, status, acknowledged_at
                """,
                (actor, message_id, actor),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"speaker message {message_id} is not addressed to {actor}")
        conn.commit()
    return dict(row)


def create_speaker_message(
    target_id: str,
    message_type: str,
    subject: str,
    body: str,
    priority: int = 50,
    target_type: str = "machine",
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into speaker_messages (target_type, target_id, message_type, subject, body, priority, metadata)
                values (%s, %s, %s, %s, %s, %s, %s::jsonb)
                returning id
                """,
                (target_type, target_id, message_type, subject, body, priority, json.dumps(metadata or {}, default=str)),
            )
            message_id = int(cur.fetchone()["id"])
        conn.commit()
    return message_id


def apply_brain_logic(event_id: int, local: bool = False) -> list[dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from listener_events where id = %s", (event_id,))
            event = cur.fetchone()
            if not event:
                raise ValueError(f"listener event {event_id} not found")
            cur.execute("update listener_events set processed_at = now() where id = %s", (event_id,))
        conn.commit()

    metadata = dict(event["metadata"] or {})
    actions: list[dict[str, Any]] = []

    if event["event_type"] in {"change_request", "deployment_request", "approval_request"}:
        approval_id = create_approval_request(
            title=event["subject"],
            request_type=event["event_type"],
            requester_machine_id=metadata.get("machine_id") or event["source_id"],
            requester_agent_id=metadata.get("agent_id") or "orchestrator",
            summary=event["body"],
            proposed_changes=metadata.get("proposed_changes", event["body"]),
            risk_level=metadata.get("risk_level", "medium"),
            metadata={"listener_event_id": event_id, **metadata},
            local=local,
        )
        message_id = create_speaker_message(
            target_id="brain-gaming-pc",
            message_type="approval_review_needed",
            subject=f"Approval review needed: {event['subject']}",
            body=f"Request {approval_id} is pending Brain audit.\n\n{event['body']}",
            priority=max(80, int(event["priority"])),
            metadata={"approval_request_id": approval_id, "listener_event_id": event_id},
            local=local,
        )
        actions.extend(
            [
                {"type": "approval_request_created", "approval_request_id": approval_id},
                {"type": "speaker_message_created", "message_id": message_id},
            ]
        )
    elif event["event_type"] == "workload_update":
        target_id = metadata.get("machine_id") or event["source_id"]
        message_id = create_speaker_message(
            target_id="brain-gaming-pc",
            message_type="workload_update",
            subject=f"Workload update from {target_id}",
            body=event["body"],
            priority=event["priority"],
            metadata={"listener_event_id": event_id, **metadata},
            local=local,
        )
        actions.append({"type": "speaker_message_created", "message_id": message_id})
    elif event["event_type"] == "task_request":
        task_id = create_manual_task(
            title=event["subject"],
            agent_id=metadata.get("agent_id", "project-coordinator"),
            category=metadata.get("category", "operations"),
            description=event["body"],
            priority=event["priority"],
            local=local,
        )
        actions.append({"type": "task_created", "task_id": task_id})
    else:
        message_id = create_speaker_message(
            target_id="brain-gaming-pc",
            message_type="listener_event",
            subject=event["subject"],
            body=event["body"],
            priority=event["priority"],
            metadata={"listener_event_id": event_id, **metadata},
            local=local,
        )
        actions.append({"type": "speaker_message_created", "message_id": message_id})

    return actions
