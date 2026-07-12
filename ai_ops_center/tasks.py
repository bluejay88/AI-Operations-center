from __future__ import annotations

from typing import Any

from .db import connect
from .orchestrator import create_task


DEV_KICKOFF_TASKS = [
    {
        "title": "Verify Dev Agent repository sync and worker health",
        "agent_id": "code-reviewer",
        "category": "development",
        "description": (
            "Confirm the laptop has pulled the latest GitHub repo, the worker is running, "
            "and the brain can see current heartbeats."
        ),
        "priority": 92,
    },
    {
        "title": "Prepare website-builder revenue package scaffold",
        "agent_id": "website-builder",
        "category": "revenue",
        "description": (
            "Create the planning outline for a small-business website package: offer, pages, "
            "pricing, delivery steps, maintenance plan, and deployment checklist."
        ),
        "priority": 86,
    },
    {
        "title": "Run implementation readiness review",
        "agent_id": "programmer",
        "category": "development",
        "description": (
            "Review the AI Operations Center codebase and list the next implementation tasks "
            "needed to move from planning-pass workers to production tool execution."
        ),
        "priority": 82,
    },
]


def task_snapshot(limit: int = 50, local: bool = False) -> list[dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.id, t.title, t.agent_id, a.machine_id, t.category, t.priority,
                    t.status, t.description, t.result, t.created_at, t.started_at,
                    t.completed_at, t.updated_at
                from tasks t
                join agents a on a.id = t.agent_id
                order by
                    case t.status
                        when 'running' then 0
                        when 'queued' then 1
                        when 'completed' then 2
                        else 3
                    end,
                    t.priority desc,
                    t.created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def create_manual_task(
    title: str,
    agent_id: str,
    category: str,
    description: str,
    priority: int,
    local: bool = False,
) -> int:
    return create_task(
        title=title,
        agent_id=agent_id,
        category=category,
        description=description,
        priority=priority,
        metadata={"created_by": "dashboard"},
        local=local,
    )


def create_dev_kickoff(local: bool = False) -> list[int]:
    created = []
    for task in DEV_KICKOFF_TASKS:
        created.append(create_task(**task, metadata={"created_by": "dashboard-dev-kickoff"}, local=local))
    return created
