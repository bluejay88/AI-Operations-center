from __future__ import annotations

import json
from typing import Any

from .approvals import create_approval_request
from .brain_bus import create_speaker_message, submit_listener_event
from .db import connect
from .remote_ops import request_remote_operation


REQUIRED_HANDOFF_RUBRIC = [
    "objective",
    "evidence",
    "current_status",
    "next_action",
    "risks",
    "approval_state",
]


def create_laptop_handoff(
    from_machine_id: str,
    to_machine_id: str,
    task_id: int | None,
    summary: str,
    evidence: dict[str, Any] | None = None,
    requested_by: str = "brain-gaming-pc",
    priority: int = 80,
    local: bool = False,
) -> dict[str, Any]:
    evidence = evidence or {}
    missing = [item for item in REQUIRED_HANDOFF_RUBRIC if not evidence.get(item)]
    status = "pending_approval" if missing else "approved"

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                """
                insert into laptop_handoffs (
                    from_machine_id, to_machine_id, task_id, requested_by, status,
                    summary, evidence, missing_rubric, priority
                )
                values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                returning *
                """,
                (
                    from_machine_id,
                    to_machine_id,
                    task_id,
                    requested_by,
                    status,
                    summary,
                    json.dumps(evidence, default=str),
                    json.dumps(missing),
                    priority,
                ),
            )
            handoff = dict(cur.fetchone())
        conn.commit()

    if missing:
        approval_id = create_approval_request(
            title=f"Handoff needs rubric evidence: {from_machine_id} to {to_machine_id}",
            request_type="laptop_handoff",
            requester_machine_id=from_machine_id,
            requester_agent_id=requested_by,
            risk_level="medium",
            summary=summary,
            proposed_changes=f"Pass task {task_id or 'n/a'} from {from_machine_id} to {to_machine_id}. Missing rubric: {', '.join(missing)}",
            metadata={"handoff_id": handoff["id"], "missing_rubric": missing, "to_machine_id": to_machine_id},
            local=local,
        )
        handoff["approval_request_id"] = approval_id
    else:
        message_id = create_speaker_message(
            target_id=to_machine_id,
            message_type="approved_laptop_handoff",
            subject=f"Approved handoff from {from_machine_id}",
            body=_handoff_body(handoff),
            priority=priority,
            metadata={"handoff_id": handoff["id"], "from_machine_id": from_machine_id, "task_id": task_id},
            local=local,
        )
        handoff["speaker_message_id"] = message_id

    submit_listener_event(
        source_type="brain",
        source_id="collaboration-router",
        event_type="workload_update",
        subject=f"Laptop handoff {status}: {from_machine_id} to {to_machine_id}",
        body=summary,
        priority=priority,
        metadata={"handoff_id": handoff["id"], "status": status, "missing_rubric": missing},
        local=local,
    )
    return handoff


def collaboration_snapshot(limit: int = 50, local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                """
                select *
                from laptop_handoffs
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            handoffs = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select *
                from laptop_model_sessions
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            sessions = [dict(row) for row in cur.fetchall()]
    return {"handoffs": handoffs, "model_sessions": sessions, "rubric": REQUIRED_HANDOFF_RUBRIC}


def create_laptop_model_session(
    machine_id: str,
    purpose: str,
    prompt: str,
    providers: list[str] | None = None,
    requested_by: str = "brain-gaming-pc",
    priority: int = 80,
    local: bool = False,
) -> dict[str, Any]:
    providers = providers or ["openai", "groq"]
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                """
                insert into laptop_model_sessions (
                    machine_id, requested_by, purpose, prompt, providers, status, priority
                )
                values (%s, %s, %s, %s, %s::jsonb, 'queued', %s)
                returning *
                """,
                (machine_id, requested_by, purpose, prompt, json.dumps(providers), priority),
            )
            session = dict(cur.fetchone())
        conn.commit()

    message_id = create_speaker_message(
        target_id=machine_id,
        message_type="model_chat_session",
        subject=f"Model support session: {purpose}",
        body=(
            "Use the Brain model router/provider workflow for this task. "
            "Return evidence, model recommendations, risks, and next action.\n\n"
            f"Prompt:\n{prompt}"
        ),
        priority=priority,
        metadata={"model_session_id": session["id"], "providers": providers, "requested_by": requested_by},
        local=local,
    )
    session["speaker_message_id"] = message_id
    return session


def request_remote_assist(
    machine_id: str,
    assist_type: str,
    summary: str,
    requested_by: str = "brain-gaming-pc",
    priority: int = 88,
    local: bool = False,
) -> dict[str, Any]:
    operation_type = {
        "browser": "remote_browser_view",
        "files": "remote_file_browse",
        "dashboard": "open_mini_dashboard",
    }.get(assist_type, assist_type)
    return request_remote_operation(
        machine_id=machine_id,
        requested_by=requested_by,
        operation_type=operation_type,
        command_summary=summary,
        priority=priority,
        metadata={"assist_type": assist_type, "brain_control": True, "requires_audit": operation_type != "open_mini_dashboard"},
        local=local,
    )


def _ensure_schema(cur: Any) -> None:
    cur.execute(
        """
        create table if not exists laptop_handoffs (
            id bigserial primary key,
            from_machine_id text not null,
            to_machine_id text not null,
            task_id bigint references tasks(id) on delete set null,
            requested_by text not null default 'brain-gaming-pc',
            status text not null default 'pending_approval',
            summary text not null,
            evidence jsonb not null default '{}',
            missing_rubric jsonb not null default '[]',
            priority integer not null default 80,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    cur.execute("create index if not exists idx_laptop_handoffs_status_time on laptop_handoffs(status, created_at desc)")
    cur.execute(
        """
        create table if not exists laptop_model_sessions (
            id bigserial primary key,
            machine_id text not null,
            requested_by text not null default 'brain-gaming-pc',
            purpose text not null,
            prompt text not null,
            providers jsonb not null default '[]',
            status text not null default 'queued',
            priority integer not null default 80,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    cur.execute("create index if not exists idx_laptop_model_sessions_machine_status on laptop_model_sessions(machine_id, status, priority desc)")


def _handoff_body(handoff: dict[str, Any]) -> str:
    return (
        f"Approved laptop-to-laptop handoff #{handoff['id']}\n"
        f"From: {handoff['from_machine_id']}\n"
        f"Task: {handoff.get('task_id') or 'n/a'}\n\n"
        f"{handoff['summary']}\n\n"
        f"Evidence:\n{json.dumps(handoff.get('evidence') or {}, indent=2, default=str)}"
    )
