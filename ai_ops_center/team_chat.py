from __future__ import annotations

import json
from typing import Any

from .db import connect


ALLOWED_ACTOR_TYPES = {"brain", "machine", "agent", "model", "human", "workflow", "system"}
ALLOWED_MESSAGE_TYPES = {
    "update",
    "decision",
    "direction",
    "question",
    "answer",
    "feedback",
    "handoff",
    "blocker",
    "model_result",
    "security",
    "audit",
}


def post_team_chat_message(
    *,
    channel: str = "operations",
    thread_key: str = "global",
    actor_type: str,
    actor_id: str,
    subject: str,
    body: str,
    machine_id: str | None = None,
    agent_id: str | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    message_type: str = "update",
    priority: int = 50,
    task_id: int | None = None,
    project_id: str | None = None,
    decision: str | None = None,
    direction: str | None = None,
    confidence: int | None = None,
    visibility: str = "internal",
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    _validate(actor_type, message_type, priority, confidence)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                """
                insert into team_chat_messages (
                    channel, thread_key, actor_type, actor_id, machine_id, agent_id,
                    model_provider, model_name, message_type, priority, task_id, project_id,
                    subject, body, decision, direction, confidence, visibility, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    channel,
                    thread_key,
                    actor_type,
                    actor_id,
                    machine_id,
                    agent_id,
                    model_provider,
                    model_name,
                    message_type,
                    priority,
                    task_id,
                    project_id,
                    subject,
                    body,
                    decision,
                    direction,
                    confidence,
                    visibility,
                    json.dumps(metadata or {}, default=str),
                ),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def team_chat_snapshot(
    *,
    channel: str | None = None,
    thread_key: str | None = None,
    machine_id: str | None = None,
    task_id: int | None = None,
    limit: int = 100,
    local: bool = False,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    filters = []
    params: list[Any] = []
    if channel:
        filters.append("channel = %s")
        params.append(channel)
    if thread_key:
        filters.append("thread_key = %s")
        params.append(thread_key)
    if machine_id:
        filters.append("machine_id = %s")
        params.append(machine_id)
    if task_id is not None:
        filters.append("task_id = %s")
        params.append(task_id)
    where = "where " + " and ".join(filters) if filters else ""
    params.append(limit)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                f"""
                select *
                from team_chat_messages
                {where}
                order by created_at desc, id desc
                limit %s
                """,
                tuple(params),
            )
            return [dict(row) for row in cur.fetchall()]


def team_chat_digest(limit: int = 40, local: bool = False) -> dict[str, Any]:
    messages = team_chat_snapshot(limit=limit, local=local)
    by_channel: dict[str, int] = {}
    by_actor_type: dict[str, int] = {}
    decisions = []
    blockers = []
    for message in messages:
        by_channel[message["channel"]] = by_channel.get(message["channel"], 0) + 1
        by_actor_type[message["actor_type"]] = by_actor_type.get(message["actor_type"], 0) + 1
        if message.get("decision"):
            decisions.append(message)
        if message.get("message_type") == "blocker":
            blockers.append(message)
    return {
        "messages": messages,
        "summary": {
            "returned": len(messages),
            "by_channel": by_channel,
            "by_actor_type": by_actor_type,
            "recent_decisions": decisions[:10],
            "recent_blockers": blockers[:10],
        },
    }


def _validate(actor_type: str, message_type: str, priority: int, confidence: int | None) -> None:
    if actor_type not in ALLOWED_ACTOR_TYPES:
        raise ValueError(f"actor_type must be one of {sorted(ALLOWED_ACTOR_TYPES)}")
    if message_type not in ALLOWED_MESSAGE_TYPES:
        raise ValueError(f"message_type must be one of {sorted(ALLOWED_MESSAGE_TYPES)}")
    if priority < 1 or priority > 100:
        raise ValueError("priority must be 1-100")
    if confidence is not None and (confidence < 0 or confidence > 100):
        raise ValueError("confidence must be 0-100")


def _ensure_schema(cur: Any) -> None:
    cur.execute(
        """
        create table if not exists team_chat_messages (
            id bigserial primary key,
            channel text not null default 'operations',
            thread_key text not null default 'global',
            actor_type text not null,
            actor_id text not null,
            machine_id text references machines(id) on delete set null,
            agent_id text references agents(id) on delete set null,
            model_provider text,
            model_name text,
            message_type text not null default 'update',
            priority integer not null default 50,
            task_id bigint references tasks(id) on delete set null,
            project_id text,
            subject text not null,
            body text not null,
            decision text,
            direction text,
            confidence integer,
            visibility text not null default 'internal',
            metadata jsonb not null default '{}',
            created_at timestamptz not null default now()
        )
        """
    )
    cur.execute("create index if not exists idx_team_chat_channel_time on team_chat_messages(channel, created_at desc)")
    cur.execute("create index if not exists idx_team_chat_thread_time on team_chat_messages(thread_key, created_at desc)")
    cur.execute("create index if not exists idx_team_chat_machine_time on team_chat_messages(machine_id, created_at desc)")
    cur.execute("create index if not exists idx_team_chat_task_time on team_chat_messages(task_id, created_at desc)")
