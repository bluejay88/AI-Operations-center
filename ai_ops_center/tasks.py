from __future__ import annotations

from datetime import UTC, datetime
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


INTAKE_AGENT_ROUTES = [
    ("development", "programmer", "dev-laptop", ["code", "api", "react", "python", "deploy", "website", "app", "database"]),
    ("research", "research-lead", "research-laptop", ["research", "market", "grant", "funding", "zillow", "reddit", "github", "academic"]),
    ("business", "business-manager", "business-laptop", ["business", "crm", "invoice", "email", "sales", "bookkeeping", "llc"]),
    ("revenue", "lead-generation", "business-laptop", ["lead", "client", "offer", "campaign", "marketing", "sales funnel"]),
    ("content", "content-engine", "brain-gaming-pc", ["content", "blog", "video", "social", "youtube", "tiktok"]),
    ("security", "security-monitor", "brain-gaming-pc", ["security", "audit", "password", "ssh", "token", "permission"]),
]

INTAKE_RUBRIC = [
    "Market relevance: include target buyer, demand signal, competitor/context note, and revenue path.",
    "Quality minimum: produce concrete deliverables, source notes, next action, blocker list, and confidence score.",
    "Security minimum: do not send emails, spend money, deploy externally, or change sensitive settings without Brain/human approval.",
    "Handoff minimum: include files changed or artifacts created, tests/checks run, and what another laptop can continue.",
    "Brain review minimum: summarize risks, assumptions, due time, and approval request if needed.",
]


def create_chat_task_intake(
    title: str,
    body: str,
    priority: int = 85,
    requester: str = "chat",
    local: bool = False,
) -> list[int]:
    text = f"{title}\n{body}".lower()
    selected = []
    for category, agent_id, machine_id, keywords in INTAKE_AGENT_ROUTES:
        if any(keyword in text for keyword in keywords):
            selected.append((category, agent_id, machine_id))
    if not selected:
        selected = [
            ("operations", "project-coordinator", "brain-gaming-pc"),
            ("research", "research-lead", "research-laptop"),
            ("development", "programmer", "dev-laptop"),
        ]

    created: list[int] = []
    for index, (category, agent_id, machine_id) in enumerate(selected, start=1):
        task_title = f"Intake {index}: {title[:130]}"
        description = (
            f"Source request from {requester}:\n{body}\n\n"
            f"Assigned lane: {category} on {machine_id}. Produce a rich, implementation-ready work product.\n\n"
            "Required rubric:\n- " + "\n- ".join(INTAKE_RUBRIC)
        )
        created.append(
            create_task(
                title=task_title,
                agent_id=agent_id,
                category=category,
                description=description,
                priority=max(1, min(100, priority - index + 1)),
                metadata={
                    "created_by": "chat_task_intake",
                    "requester": requester,
                    "source_title": title,
                    "target_machine_id": machine_id,
                    "rubric": INTAKE_RUBRIC,
                    "dedupe_hint": f"{requester}:{title}".lower(),
                },
                local=local,
            )
        )
    return created


def task_snapshot(limit: int = 50, local: bool = False) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.id, t.title, t.agent_id, coalesce(t.execution_machine_id, a.machine_id) as machine_id, t.category, t.priority,
                    t.status, t.description, t.result, t.created_at, t.started_at,
                    t.completed_at, t.updated_at, t.execution_machine_id,
                    t.claimed_by_machine, t.lease_expires_at, t.attempt_count,
                    t.max_attempts, t.next_attempt_at, t.assignment_generation, t.last_error
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


def task_summary(local: bool = False) -> dict[str, Any]:
    """Return lifetime task totals independently of the recent-task list limit."""
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select coalesce(t.execution_machine_id, a.machine_id) as machine_id, t.status, count(*) as count
                from tasks t
                left join agents a on a.id = t.agent_id
                group by coalesce(t.execution_machine_id, a.machine_id), t.status
                order by coalesce(t.execution_machine_id, a.machine_id), t.status
                """
            )
            rows = [dict(row) for row in cur.fetchall()]
    return _build_task_summary(rows)


def _build_task_summary(
    rows: list[dict[str, Any]], generated_at: datetime | None = None
) -> dict[str, Any]:
    statuses = ("queued", "running", "completed", "failed", "cancelled")
    status_counts = {status: 0 for status in statuses}
    by_machine: dict[str, dict[str, int]] = {}
    total = 0
    for row in rows:
        machine_id = str(row.get("machine_id") or "unassigned")
        status = str(row.get("status") or "unknown")
        count = int(row.get("count") or 0)
        bucket = by_machine.setdefault(machine_id, {item: 0 for item in statuses})
        bucket[status] = bucket.get(status, 0) + count
        bucket["total"] = bucket.get("total", 0) + count
        status_counts[status] = status_counts.get(status, 0) + count
        total += count
    completed_by_machine = sum(bucket.get("completed", 0) for bucket in by_machine.values())
    status_total = sum(status_counts.values())
    return {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "total": total,
        "completed_total": status_counts["completed"],
        "active_total": status_counts["queued"] + status_counts["running"],
        "status_counts": status_counts,
        "by_machine": by_machine,
        "contract": {
            "version": 1,
            "scope": "lifetime",
            "source": "database_aggregate",
            "recent_list_independent": True,
            "invariants": {
                "completed_equals_machine_sum": status_counts["completed"] == completed_by_machine,
                "total_equals_status_sum": total == status_total,
            },
        },
    }


def task_accounting_audit(
    summary: dict[str, Any],
    recent_returned: int | None = None,
    readiness_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invariants = summary.get("contract", {}).get("invariants", {})
    rubric = {
        "lifetime_scope": summary.get("contract", {}).get("scope") == "lifetime",
        "database_aggregate_source": summary.get("contract", {}).get("source") == "database_aggregate",
        "recent_list_independent": bool(summary.get("contract", {}).get("recent_list_independent")),
        "global_per_machine_reconciled": bool(invariants.get("completed_equals_machine_sum")),
        "all_statuses_reconciled": bool(invariants.get("total_equals_status_sum")),
        "readiness_parity": readiness_summary is None
        or int(readiness_summary.get("completed_total", -1)) == int(summary.get("completed_total", -2)),
    }
    return {
        "contract_version": 1,
        "stage": "completed_task_accounting",
        "status": "passed" if all(rubric.values()) else "failed",
        "rubric": rubric,
        "evidence": {
            "completed_total": int(summary.get("completed_total", 0)),
            "machine_count": len(summary.get("by_machine", {})),
            "recent_rows_returned": recent_returned,
        },
    }


def task_detail(task_id: int, local: bool = False) -> dict[str, Any] | None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.id, t.title, t.agent_id, coalesce(t.execution_machine_id, a.machine_id) as machine_id, t.category, t.priority,
                    t.status, t.description, t.result, t.created_at, t.started_at,
                    t.completed_at, t.updated_at, t.execution_machine_id,
                    t.claimed_by_machine, t.claim_token, t.lease_expires_at,
                    t.attempt_count, t.max_attempts, t.next_attempt_at,
                    t.assignment_generation, t.last_error
                from tasks t
                join agents a on a.id = t.agent_id
                where t.id = %s
                """,
                (task_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


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
