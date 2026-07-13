from __future__ import annotations

import json
import threading
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

PEER_REQUEST_TYPES = {
    "research",
    "asset",
    "content",
    "stats",
    "code_review",
    "qa",
    "security_review",
    "business_input",
    "diagnostic",
    "handoff_help",
}

_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY = False


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
            _ensure_schema_once(cur)
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
            _ensure_schema_once(cur)
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
            cur.execute(
                """
                select *
                from peer_requests
                order by
                    case status
                        when 'requested' then 0
                        when 'in_progress' then 1
                        when 'fulfilled' then 2
                        else 3
                    end,
                    priority desc,
                    created_at desc
                limit %s
                """,
                (limit,),
            )
            peer_requests = [dict(row) for row in cur.fetchall()]
    return {
        "handoffs": handoffs,
        "model_sessions": sessions,
        "peer_requests": peer_requests,
        "rubric": REQUIRED_HANDOFF_RUBRIC,
        "peer_request_types": sorted(PEER_REQUEST_TYPES),
    }


def create_peer_request(
    from_machine_id: str,
    to_machine_id: str,
    request_type: str,
    subject: str,
    body: str,
    requested_by: str = "brain-gaming-pc",
    task_id: int | None = None,
    project_id: str | None = None,
    priority: int = 80,
    due_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    if request_type not in PEER_REQUEST_TYPES:
        raise ValueError(f"request_type must be one of {sorted(PEER_REQUEST_TYPES)}")
    metadata = metadata or {}
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema_once(cur)
            cur.execute(
                """
                insert into peer_requests (
                    from_machine_id, to_machine_id, requested_by, request_type, subject,
                    body, task_id, project_id, priority, due_at, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, nullif(%s, '')::timestamptz, %s::jsonb)
                returning *
                """,
                (
                    from_machine_id,
                    to_machine_id,
                    requested_by,
                    request_type,
                    subject,
                    body,
                    task_id,
                    project_id,
                    priority,
                    due_at or "",
                    json.dumps(metadata, default=str),
                ),
            )
            peer_request = dict(cur.fetchone())
            if task_id is not None:
                cur.execute(
                    """
                    update tasks
                    set metadata = metadata || jsonb_build_object('peer_request_id', %s::bigint),
                        updated_at = now()
                    where id = %s and execution_machine_id = %s
                    """,
                    (peer_request["id"], task_id, to_machine_id),
                )
                if cur.rowcount != 1:
                    raise ValueError(f"task {task_id} is not assigned to {to_machine_id}")
        conn.commit()

    message_id = create_speaker_message(
        target_id=to_machine_id,
        message_type="peer_request",
        subject=f"Peer request from {from_machine_id}: {subject}",
        body=_peer_request_body(peer_request),
        priority=priority,
        metadata={"peer_request_id": peer_request["id"], "from_machine_id": from_machine_id, "request_type": request_type},
        local=local,
    )
    peer_request["speaker_message_id"] = message_id
    submit_listener_event(
        source_type="brain",
        source_id="peer-request-router",
        event_type="workload_update",
        subject=f"Peer request routed: {from_machine_id} to {to_machine_id}",
        body=f"{request_type}: {subject}",
        priority=priority,
        metadata={"peer_request_id": peer_request["id"], "status": "requested"},
        local=local,
    )
    return peer_request


def respond_to_peer_request(
    request_id: int,
    responder_machine_id: str,
    response_body: str,
    status: str = "fulfilled",
    artifacts: list[str] | None = None,
    quality_score: int | None = None,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    if status not in {"in_progress", "fulfilled", "needs_clarification", "rejected"}:
        raise ValueError("status must be in_progress, fulfilled, needs_clarification, or rejected")
    artifacts = artifacts or []
    metadata = metadata or {}
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema_once(cur)
            cur.execute(
                """
                update peer_requests
                set status = %s,
                    response_body = %s,
                    artifacts = %s::jsonb,
                    quality_score = %s,
                    responder_machine_id = %s,
                    response_metadata = %s::jsonb,
                    responded_at = case when %s in ('fulfilled', 'rejected') then now() else responded_at end,
                    updated_at = now()
                where id = %s and to_machine_id = %s
                returning *
                """,
                (
                    status,
                    response_body,
                    json.dumps(artifacts),
                    quality_score,
                    responder_machine_id,
                    json.dumps(metadata, default=str),
                    status,
                    request_id,
                    responder_machine_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"peer request {request_id} is not addressed to {responder_machine_id}")
            peer_request = dict(row)
        conn.commit()

    create_speaker_message(
        target_id=peer_request["from_machine_id"],
        message_type=f"peer_request_{status}",
        subject=f"Peer response from {responder_machine_id}: {peer_request['subject']}",
        body=response_body,
        priority=peer_request.get("priority") or 80,
        metadata={"peer_request_id": request_id, "status": status, "artifacts": artifacts, "quality_score": quality_score},
        local=local,
    )
    submit_listener_event(
        source_type="machine",
        source_id=responder_machine_id,
        event_type="peer_request_response",
        subject=f"Peer request {request_id} {status}",
        body=response_body,
        priority=peer_request.get("priority") or 80,
        metadata={"peer_request_id": request_id, "status": status, "artifacts": artifacts, "quality_score": quality_score},
        local=local,
    )
    return peer_request


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
            _ensure_schema_once(cur)
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


def _ensure_schema_once(cur: Any) -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return
        _ensure_schema(cur)
        _SCHEMA_READY = True


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
    cur.execute(
        """
        create table if not exists peer_requests (
            id bigserial primary key,
            from_machine_id text not null,
            to_machine_id text not null,
            requested_by text not null default 'brain-gaming-pc',
            request_type text not null,
            subject text not null,
            body text not null,
            task_id bigint references tasks(id) on delete set null,
            project_id text,
            priority integer not null default 80,
            status text not null default 'requested',
            due_at timestamptz,
            metadata jsonb not null default '{}',
            response_body text,
            artifacts jsonb not null default '[]',
            quality_score integer,
            responder_machine_id text,
            response_metadata jsonb not null default '{}',
            responded_at timestamptz,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    cur.execute("create index if not exists idx_peer_requests_target_status on peer_requests(to_machine_id, status, priority desc, created_at desc)")
    cur.execute("create index if not exists idx_peer_requests_source_time on peer_requests(from_machine_id, created_at desc)")


def _handoff_body(handoff: dict[str, Any]) -> str:
    return (
        f"Approved laptop-to-laptop handoff #{handoff['id']}\n"
        f"From: {handoff['from_machine_id']}\n"
        f"Task: {handoff.get('task_id') or 'n/a'}\n\n"
        f"{handoff['summary']}\n\n"
        f"Evidence:\n{json.dumps(handoff.get('evidence') or {}, indent=2, default=str)}"
    )


def _peer_request_body(peer_request: dict[str, Any]) -> str:
    return (
        f"Peer request #{peer_request['id']}\n"
        f"From: {peer_request['from_machine_id']}\n"
        f"Type: {peer_request['request_type']}\n"
        f"Task: {peer_request.get('task_id') or 'n/a'}\n"
        f"Due: {peer_request.get('due_at') or 'not set'}\n\n"
        f"{peer_request['body']}\n\n"
        "Respond through POST /collaboration/peer-requests/{id}/respond with status, response_body, artifacts, and quality_score."
    )
