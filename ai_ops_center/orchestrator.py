from __future__ import annotations

import json
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import load_revenue_strategy
from .db import connect


PRIORITY_TASKS = [
    {
        "title": "Create today's AI team priorities",
        "agent_id": "chief-of-staff",
        "category": "operations",
        "priority": 100,
        "description": "Summarize deadlines, projects, goals, calendar items, blocked tasks, and top revenue moves.",
    },
    {
        "title": "Find 10 revenue leads for website or AI maintenance packages",
        "agent_id": "lead-generation",
        "category": "revenue",
        "priority": 95,
        "description": "Identify small businesses likely to need website, automation, or content support. Store source, fit, offer, and next step.",
    },
    {
        "title": "Produce grant and funding watchlist",
        "agent_id": "grant-scout",
        "category": "research",
        "priority": 90,
        "description": "Find grants, Illinois business opportunities, and government funding deadlines relevant to the business.",
    },
    {
        "title": "Draft one sellable digital product concept",
        "agent_id": "digital-products",
        "category": "revenue",
        "priority": 88,
        "description": "Define target buyer, title, promise, outline, price, distribution path, and build checklist.",
    },
    {
        "title": "Run codebase health check",
        "agent_id": "code-reviewer",
        "category": "development",
        "priority": 80,
        "description": "Run tests, inspect open changes, identify security or deployment risks, and write a concise report.",
    },
]


def create_task(
    title: str,
    agent_id: str,
    category: str,
    description: str,
    priority: int = 50,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tasks (
                    title, agent_id, category, description, priority, metadata, execution_machine_id
                )
                values (%s, %s, %s, %s, %s, %s::jsonb, (select machine_id from agents where id = %s))
                returning id
                """,
                (title, agent_id, category, description, priority, json.dumps(metadata or {}), agent_id),
            )
            task_id = cur.fetchone()["id"]
        conn.commit()
    return int(task_id)


def create_daily_priorities(local: bool = False) -> list[int]:
    strategy = load_revenue_strategy()
    created: list[int] = []
    for task in PRIORITY_TASKS:
        task_id = create_task(
            **task,
            metadata={
                "generated_by": "orchestrator",
                "target_revenue": strategy.get("annual_revenue_target", {}),
                "created_for_date": datetime.now(UTC).date().isoformat(),
            },
            local=local,
        )
        created.append(task_id)
    return created


def claim_next_task(machine_id: str, local: bool = False, lease_seconds: int = 120) -> dict[str, Any] | None:
    if lease_seconds < 30 or lease_seconds > 3600:
        raise ValueError("lease_seconds must be between 30 and 3600")
    claim_token = str(uuid.uuid4())
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with next_task as (
                    select t.id
                    from tasks t
                    join agents a on a.id = t.agent_id
                    where t.status = 'queued'
                      and coalesce(t.execution_machine_id, a.machine_id) = %s
                      and (t.next_attempt_at is null or t.next_attempt_at <= now())
                      and lower(coalesce(t.metadata->>'queue_state', '')) not in ('pending_approval', 'approval_required', 'blocked')
                      and (
                        lower(coalesce(t.metadata->>'requires_approval', 'false')) not in ('1', 'true', 'yes')
                        or lower(coalesce(t.metadata->>'approval_status', '')) in ('approved', 'deployed')
                      )
                    order by
                      (t.priority + least(20, floor(extract(epoch from (now() - t.created_at)) / 3600))) desc,
                      t.created_at asc
                    for update skip locked
                    limit 1
                )
                update tasks t
                set status = 'running', started_at = now(), updated_at = now(),
                    execution_machine_id = %s, claimed_by_machine = %s,
                    claim_token = %s, lease_expires_at = now() + (%s * interval '1 second'),
                    attempt_count = attempt_count + 1, next_attempt_at = null, last_error = null
                from next_task
                where t.id = next_task.id
                returning t.*
                """,
                (machine_id, machine_id, machine_id, claim_token, lease_seconds),
            )
            task = cur.fetchone()
            if task:
                cur.execute(
                    """
                    insert into task_events (task_id, event_type, message)
                    values (%s, 'claimed', %s)
                    """,
                    (task["id"], f"{machine_id} claimed task {task['id']}; lease_token={claim_token[:8]}."),
                )
                cur.execute(
                    "update machine_status_current set active_task_id = %s, updated_at = now() where machine_id = %s",
                    (task["id"], machine_id),
                )
        conn.commit()
    return task


def complete_task(task_id: int, result: str, claim_token: str, machine_id: str, local: bool = False) -> bool:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update tasks
                set status = 'completed',
                    result = %s,
                    completed_at = now(),
                    claim_token = null,
                    lease_expires_at = null,
                    updated_at = now()
                where id = %s
                  and status = 'running'
                  and claim_token = %s
                  and claimed_by_machine = %s
                returning id
                """,
                (result, task_id, claim_token, machine_id),
            )
            completed = cur.fetchone()
            if not completed:
                conn.rollback()
                return False
            cur.execute(
                """
                insert into task_events (task_id, event_type, message)
                values (%s, 'completed', %s)
                """,
                (task_id, result[:1000]),
            )
            cur.execute(
                "update machine_status_current set active_task_id = null, updated_at = now() where machine_id = %s and active_task_id = %s",
                (machine_id, task_id),
            )
        conn.commit()
    return True


def renew_task_lease(
    task_id: int,
    claim_token: str,
    machine_id: str,
    lease_seconds: int = 120,
    local: bool = False,
) -> bool:
    if lease_seconds < 30 or lease_seconds > 3600:
        raise ValueError("lease_seconds must be between 30 and 3600")
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update tasks
                set lease_expires_at = now() + (%s * interval '1 second'), updated_at = now()
                where id = %s and status = 'running'
                  and claim_token = %s and claimed_by_machine = %s
                returning id
                """,
                (lease_seconds, task_id, claim_token, machine_id),
            )
            renewed = cur.fetchone() is not None
        conn.commit()
    return renewed


def fail_task(task_id: int, error: str, claim_token: str, machine_id: str, local: bool = False) -> str:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select attempt_count, max_attempts from tasks where id = %s and status = 'running' and claim_token = %s and claimed_by_machine = %s for update",
                (task_id, claim_token, machine_id),
            )
            task = cur.fetchone()
            if not task:
                conn.rollback()
                return "rejected_stale_claim"
            attempts = int(task["attempt_count"])
            terminal = attempts >= int(task["max_attempts"])
            if terminal:
                status = "failed"
                next_attempt_at = None
            else:
                from .queue_manager import retry_delay_seconds

                status = "queued"
                next_attempt_at = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds(attempts))
            cur.execute(
                """
                update tasks
                set status = %s, started_at = null, claim_token = null, claimed_by_machine = null,
                    lease_expires_at = null, next_attempt_at = %s, last_error = %s, updated_at = now()
                where id = %s
                """,
                (status, next_attempt_at, error[:2000], task_id),
            )
            cur.execute(
                "insert into task_events (task_id, event_type, message) values (%s, %s, %s)",
                (task_id, "dead_lettered" if terminal else "retry_scheduled", error[:1000]),
            )
            cur.execute(
                "update machine_status_current set active_task_id = null, updated_at = now() where machine_id = %s and active_task_id = %s",
                (machine_id, task_id),
            )
        conn.commit()
    return status


def record_heartbeat(machine_id: str, status: str = "online", active_task_id: int | None = None, local: bool = False) -> None:
    hostname = socket.gethostname()
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into machine_status_current (machine_id, status, last_seen_at, hostname, active_task_id, updated_at)
                values (%s, %s, now(), %s, %s, now())
                on conflict (machine_id) do update set
                    status = excluded.status,
                    last_seen_at = excluded.last_seen_at,
                    hostname = excluded.hostname,
                    active_task_id = excluded.active_task_id,
                    updated_at = now()
                """,
                (machine_id, status, hostname, active_task_id),
            )
            cur.execute(
                """
                insert into machine_heartbeats (machine_id, status)
                values (%s, %s)
                """,
                (machine_id, status),
            )
        conn.commit()
