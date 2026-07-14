from __future__ import annotations

import json
from typing import Any

from .approvals import create_approval_request
from .db import connect
from .phoenix import laptop_instruction, phoenix_briefing
from .tasks import create_manual_task
from .team_chat import post_team_chat_message


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
            dedupe_key = str(metadata.get("dedupe_key") or "").strip()
            if dedupe_key:
                dedupe_window_seconds = max(1, min(int(metadata.get("dedupe_window_seconds", 300)), 86400))
                cur.execute(
                    """
                    select id
                    from listener_events
                    where source_type = %s
                      and source_id = %s
                      and event_type = %s
                      and metadata->>'dedupe_key' = %s
                      and created_at >= now() - make_interval(secs => %s)
                    order by created_at desc
                    limit 1
                    """,
                    (source_type, source_id, event_type, dedupe_key, dedupe_window_seconds),
                )
                duplicate = cur.fetchone()
                if duplicate:
                    return {"event_id": int(duplicate["id"]), "actions": [], "deduplicated": True}
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

    _mirror_listener_to_team_chat(
        source_type=source_type,
        source_id=source_id,
        event_type=event_type,
        subject=subject,
        body=body,
        priority=priority,
        metadata=metadata,
        event_id=event_id,
        local=local,
    )
    actions = apply_brain_logic(event_id, local=local)
    return {"event_id": event_id, "actions": actions, "deduplicated": False}


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
    _mirror_speaker_to_team_chat(
        target_id=target_id,
        message_type=message_type,
        subject=subject,
        body=body,
        priority=priority,
        metadata=metadata or {},
        message_id=message_id,
        local=local,
    )
    return message_id


def _mirror_listener_to_team_chat(
    *,
    source_type: str,
    source_id: str,
    event_type: str,
    subject: str,
    body: str,
    priority: int,
    metadata: dict[str, Any],
    event_id: int,
    local: bool,
) -> None:
    try:
        post_team_chat_message(
            channel=str(metadata.get("channel") or "operations"),
            thread_key=str(metadata.get("thread_key") or metadata.get("task_id") or "global"),
            actor_type=_actor_type(source_type),
            actor_id=source_id,
            machine_id=source_id if source_type == "machine" else metadata.get("machine_id"),
            agent_id=metadata.get("agent_id"),
            message_type=_team_message_type(event_type),
            priority=priority,
            task_id=_int_or_none(metadata.get("task_id")),
            project_id=metadata.get("project_id"),
            subject=subject,
            body=body,
            decision=metadata.get("decision"),
            direction=metadata.get("direction"),
            confidence=_int_or_none(metadata.get("confidence")),
            metadata={**metadata, "listener_event_id": event_id, "mirrored_from": "listener"},
            local=local,
        )
    except Exception:
        return


def _mirror_speaker_to_team_chat(
    *,
    target_id: str,
    message_type: str,
    subject: str,
    body: str,
    priority: int,
    metadata: dict[str, Any],
    message_id: int,
    local: bool,
) -> None:
    try:
        post_team_chat_message(
            channel=str(metadata.get("channel") or "operations"),
            thread_key=str(metadata.get("thread_key") or metadata.get("task_id") or "global"),
            actor_type="brain",
            actor_id="brain-gaming-pc",
            machine_id=target_id if target_id.endswith("-laptop") else metadata.get("machine_id"),
            agent_id=metadata.get("agent_id"),
            message_type=_team_message_type(message_type),
            priority=priority,
            task_id=_int_or_none(metadata.get("task_id")),
            project_id=metadata.get("project_id"),
            subject=subject,
            body=body,
            decision=metadata.get("decision"),
            direction=metadata.get("direction") or body,
            confidence=_int_or_none(metadata.get("confidence")),
            metadata={**metadata, "speaker_message_id": message_id, "target_id": target_id, "mirrored_from": "speaker"},
            local=local,
        )
    except Exception:
        return


def _actor_type(value: str) -> str:
    return value if value in {"brain", "machine", "agent", "model", "human", "workflow", "system"} else "system"


def _team_message_type(value: str) -> str:
    lowered = value.lower()
    if "approval" in lowered or "decision" in lowered:
        return "decision"
    if "completed" in lowered or "response" in lowered or "result" in lowered:
        return "answer"
    if "error" in lowered or "blocker" in lowered or "failed" in lowered:
        return "blocker"
    if "security" in lowered:
        return "security"
    if "audit" in lowered:
        return "audit"
    if "request" in lowered or "question" in lowered:
        return "question"
    if "model" in lowered:
        return "model_result"
    return "update"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value) != "" else None
    except (TypeError, ValueError):
        return None


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
    elif event["event_type"] == "speaker_message_received":
        actions.append(
            {
                "type": "speaker_receipt_recorded",
                "message_id": metadata.get("speaker_message_id"),
                "machine_id": metadata.get("machine_id") or event["source_id"],
            }
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
