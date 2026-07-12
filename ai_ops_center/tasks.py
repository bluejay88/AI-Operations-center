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


BUSINESS_CONTINUITY_TASKS = [
    {
        "title": "Build the first AI website maintenance offer",
        "agent_id": "website-builder",
        "category": "revenue",
        "description": (
            "Create a concrete service package for small businesses: offer name, included pages, "
            "monthly maintenance scope, setup price, recurring price, fulfillment checklist, and launch criteria."
        ),
        "priority": 98,
    },
    {
        "title": "Create a small-business lead research list",
        "agent_id": "research-lead",
        "category": "revenue",
        "description": (
            "Research target niches and produce a lead-source plan for 30 local small businesses that likely need "
            "website refresh, automation, content, or maintenance services. Do not send outreach."
        ),
        "priority": 96,
    },
    {
        "title": "Draft outreach copy for website maintenance prospects",
        "agent_id": "content-engine",
        "category": "revenue",
        "description": (
            "Draft human-review-only outreach assets: one short email, one LinkedIn message, one phone script, "
            "and one follow-up. Include approval guardrails before anything is sent."
        ),
        "priority": 94,
    },
    {
        "title": "Design the business operating scorecard",
        "agent_id": "project-coordinator",
        "category": "business",
        "description": (
            "Define the dashboard metrics needed to run toward $250k-$500k annual revenue: leads, replies, calls, "
            "proposals, closes, MRR, delivery time, margin, cash flow, and weekly review cadence."
        ),
        "priority": 92,
    },
    {
        "title": "Prepare grant and funding opportunities for business launch",
        "agent_id": "grant-scout",
        "category": "research",
        "description": (
            "Build a funding watchlist for Illinois, small-business, technology, workforce, and digital services grants. "
            "Capture eligibility, deadline, award range, source URL, and next step."
        ),
        "priority": 90,
    },
    {
        "title": "Create reusable digital product launch plan",
        "agent_id": "digital-products",
        "category": "revenue",
        "description": (
            "Define one digital product that can be built quickly from existing AI Ops knowledge: title, buyer, promise, "
            "outline, format, price, upsell path, and production checklist."
        ),
        "priority": 88,
    },
    {
        "title": "Review implementation path for production worker tools",
        "agent_id": "programmer",
        "category": "development",
        "description": (
            "Break down the implementation work needed for agents to create files, reports, websites, and business artifacts "
            "as real outputs rather than planning-pass text."
        ),
        "priority": 86,
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


def create_business_continuity(local: bool = False) -> list[int]:
    created = []
    for task in BUSINESS_CONTINUITY_TASKS:
        created.append(
            create_task(
                **task,
                metadata={
                    "created_by": "business-continuity",
                    "reason": "Business laptop is not online; distribute business-building work to available machines.",
                },
                local=local,
            )
        )
    return created
