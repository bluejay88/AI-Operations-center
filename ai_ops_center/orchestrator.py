from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
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
                insert into tasks (title, agent_id, category, description, priority, metadata)
                values (%s, %s, %s, %s, %s, %s::jsonb)
                returning id
                """,
                (title, agent_id, category, description, priority, json.dumps(metadata or {})),
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


def claim_next_task(machine_id: str, local: bool = False) -> dict[str, Any] | None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with next_task as (
                    select t.id
                    from tasks t
                    join agents a on a.id = t.agent_id
                    where t.status = 'queued'
                      and a.machine_id = %s
                    order by t.priority desc, t.created_at asc
                    for update skip locked
                    limit 1
                )
                update tasks t
                set status = 'running', started_at = now(), updated_at = now()
                from next_task
                where t.id = next_task.id
                returning t.*
                """,
                (machine_id,),
            )
            task = cur.fetchone()
            if task:
                cur.execute(
                    """
                    insert into task_events (task_id, event_type, message)
                    values (%s, 'claimed', %s)
                    """,
                    (task["id"], f"{machine_id} claimed task {task['id']}"),
                )
        conn.commit()
    return task


def complete_task(task_id: int, result: str, local: bool = False) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update tasks
                set status = 'completed',
                    result = %s,
                    completed_at = now(),
                    updated_at = now()
                where id = %s
                """,
                (result, task_id),
            )
            cur.execute(
                """
                insert into task_events (task_id, event_type, message)
                values (%s, 'completed', %s)
                """,
                (task_id, result[:1000]),
            )
        conn.commit()


def record_heartbeat(machine_id: str, status: str = "online", local: bool = False) -> None:
    hostname = socket.gethostname()
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into machine_status_current (machine_id, status, last_seen_at, hostname, updated_at)
                values (%s, %s, now(), %s, now())
                on conflict (machine_id) do update set
                    status = excluded.status,
                    last_seen_at = excluded.last_seen_at,
                    hostname = excluded.hostname,
                    updated_at = now()
                """,
                (machine_id, status, hostname),
            )
            cur.execute(
                """
                insert into machine_heartbeats (machine_id, status)
                values (%s, %s)
                """,
                (machine_id, status),
            )
        conn.commit()
