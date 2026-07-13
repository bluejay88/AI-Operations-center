from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .config import load_operations_2
from .db import connect
from .orchestrator import create_task


PROJECT_ID = "ai-operations-center-2"

IMPROVEMENT_OWNERS = {
    "Brain": "orchestrator",
    "Dev": "programmer",
    "Research": "research-lead",
    "Business": "business-manager",
    "Security": "code-reviewer",
    "Finance": "finance-manager",
    "Dashboard": "project-coordinator",
    "Automation": "orchestrator",
    "Revenue": "lead-generation",
    "Infrastructure": "code-reviewer",
}

IMPROVEMENT_BACKLOG = [
    ("Unified memory index", "Brain", "P0"), ("Agent intent router", "Brain", "P0"), ("Cross-agent context handoff", "Brain", "P0"),
    ("Long-term goal tracker", "Brain", "P1"), ("Decision audit trail", "Brain", "P1"), ("Prompt library registry", "Brain", "P1"),
    ("Agent confidence scoring", "Brain", "P1"), ("Knowledge freshness checker", "Brain", "P2"), ("Task decomposition engine", "Brain", "P2"),
    ("Failure pattern memory", "Brain", "P2"), ("Local dev environment audit", "Dev", "P0"), ("Standard test runner", "Dev", "P0"),
    ("API contract validation", "Dev", "P0"), ("Component health checks", "Dev", "P1"), ("Code ownership map", "Dev", "P1"),
    ("Dependency update workflow", "Dev", "P1"), ("Local smoke test suite", "Dev", "P1"), ("Error reproduction templates", "Dev", "P2"),
    ("Developer command palette", "Dev", "P2"), ("Release checklist automation", "Dev", "P2"), ("Source credibility scoring", "Research", "P0"),
    ("Competitive intelligence tracker", "Research", "P0"), ("Citation-backed report mode", "Research", "P0"), ("Industry trend monitor", "Research", "P1"),
    ("Research request queue", "Research", "P1"), ("Research summary archive", "Research", "P1"), ("Expert-source directory", "Research", "P1"),
    ("Dataset discovery workflow", "Research", "P2"), ("Research gap detector", "Research", "P2"), ("Regulatory watchlist", "Research", "P2"),
    ("Business KPI framework", "Business", "P0"), ("Operating cadence planner", "Business", "P0"), ("Weekly executive brief", "Business", "P0"),
    ("Customer segment model", "Business", "P1"), ("Vendor evaluation matrix", "Business", "P1"), ("Project ROI scoring", "Business", "P1"),
    ("Risk register workflow", "Business", "P1"), ("Decision memo generator", "Business", "P2"), ("OKR progress tracker", "Business", "P2"),
    ("Business process map", "Business", "P2"), ("Secrets inventory scan", "Security", "P0"), ("Access control review", "Security", "P0"),
    ("Threat model baseline", "Security", "P0"), ("Dependency vulnerability alerts", "Security", "P1"), ("Audit log dashboard", "Security", "P1"),
    ("Incident response playbook", "Security", "P1"), ("Data classification labels", "Security", "P1"), ("Secure config checker", "Security", "P2"),
    ("Agent permission boundaries", "Security", "P2"), ("Backup recovery drill", "Security", "P2"), ("Cash flow dashboard", "Finance", "P0"),
    ("Expense categorization", "Finance", "P0"), ("Budget variance alerts", "Finance", "P0"), ("Revenue forecast model", "Finance", "P1"),
    ("Vendor spend tracker", "Finance", "P1"), ("Unit economics calculator", "Finance", "P1"), ("Invoice status monitor", "Finance", "P1"),
    ("Tax document checklist", "Finance", "P2"), ("Scenario planning model", "Finance", "P2"), ("Financial close checklist", "Finance", "P2"),
    ("Executive command dashboard", "Dashboard", "P0"), ("Agent performance dashboard", "Dashboard", "P0"), ("System health dashboard", "Dashboard", "P0"),
    ("Revenue operations dashboard", "Dashboard", "P1"), ("Security posture dashboard", "Dashboard", "P1"), ("Research pipeline dashboard", "Dashboard", "P1"),
    ("Automation run history view", "Dashboard", "P1"), ("Task SLA dashboard", "Dashboard", "P2"), ("Data quality dashboard", "Dashboard", "P2"),
    ("Custom dashboard builder", "Dashboard", "P2"), ("Daily briefing automation", "Automation", "P0"), ("Task triage automation", "Automation", "P0"),
    ("Alert routing automation", "Automation", "P0"), ("Report generation scheduler", "Automation", "P1"), ("Email follow-up drafts", "Automation", "P1"),
    ("Meeting notes processor", "Automation", "P1"), ("Data sync automation", "Automation", "P1"), ("Regression test automation", "Automation", "P2"),
    ("Renewal reminder automation", "Automation", "P2"), ("Document filing automation", "Automation", "P2"), ("Lead scoring engine", "Revenue", "P0"),
    ("Sales pipeline tracker", "Revenue", "P0"), ("Offer testing backlog", "Revenue", "P0"), ("Pricing experiment framework", "Revenue", "P1"),
    ("Churn risk detector", "Revenue", "P1"), ("Upsell opportunity finder", "Revenue", "P1"), ("Campaign performance monitor", "Revenue", "P1"),
    ("Proposal generator", "Revenue", "P2"), ("Customer feedback miner", "Revenue", "P2"), ("Referral program tracker", "Revenue", "P2"),
    ("Environment configuration audit", "Infrastructure", "P0"), ("Backup strategy implementation", "Infrastructure", "P0"), ("Observability baseline", "Infrastructure", "P0"),
    ("Deployment pipeline hardening", "Infrastructure", "P1"), ("Database health monitor", "Infrastructure", "P1"), ("Queue and worker monitoring", "Infrastructure", "P1"),
    ("Cost monitoring alerts", "Infrastructure", "P1"), ("Service dependency map", "Infrastructure", "P2"), ("Disaster recovery runbook", "Infrastructure", "P2"),
    ("Infrastructure-as-code baseline", "Infrastructure", "P2"),
]

LAPTOP_WORKSTREAMS = {
    "dev-laptop": {
        "agents": ["programmer", "code-reviewer", "website-builder"],
        "themes": [
            "API hardening", "unit test coverage", "dashboard reliability", "database migration safety", "GitHub workflow",
            "deployment validation", "security scan automation", "developer documentation", "package release", "worker runtime",
        ],
    },
    "research-laptop": {
        "agents": ["research-lead", "grant-scout", "resale-scout", "gaming-intel"],
        "themes": [
            "grant discovery", "Illinois opportunity scan", "real estate lead research", "estate sale sourcing", "eBay arbitrage",
            "AI news brief", "competitor analysis", "academic paper scan", "government funding watchlist", "trend prediction",
        ],
    },
    "business-laptop": {
        "agents": ["business-manager", "finance-manager", "social-media", "lead-generation", "marketing-agent"],
        "themes": [
            "CRM hygiene", "invoice workflow", "cash flow report", "lead generation", "proposal drafting",
            "email campaign", "social media calendar", "sales funnel", "product listing", "customer support drafts",
        ],
    },
}


def _json(value: Any) -> str:
    return json.dumps(value, default=str)


def seed_operations_2(local: bool = False) -> dict[str, Any]:
    config = load_operations_2()
    mission = config["mission_control"]
    context_types = config["project_context_schema"]

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into projects (
                    id, name, project_type, status, owner_machine_id, owner_agent_id,
                    progress, risk_score, cost_estimate, quality_score, test_coverage,
                    revenue_target, metadata
                )
                values (%s, %s, 'platform', 'active', 'brain-gaming-pc', 'orchestrator',
                    28, 34, 0, 82, 18, 500000, %s::jsonb)
                on conflict (id) do update set
                    name = excluded.name,
                    status = excluded.status,
                    owner_machine_id = excluded.owner_machine_id,
                    owner_agent_id = excluded.owner_agent_id,
                    revenue_target = excluded.revenue_target,
                    metadata = excluded.metadata,
                    updated_at = now()
                """,
                (
                    PROJECT_ID,
                    mission["name"],
                    _json(
                        {
                            "brain_role": mission["brain_role"],
                            "principle": mission["principle"],
                            "annual_sales_goal_range": "$250,000-$500,000",
                        }
                    ),
                ),
            )

            for note_type in context_types:
                body = _default_context_body(note_type, config)
                cur.execute(
                    """
                    insert into project_notes (project_id, note_type, title, body, source, metadata)
                    select %s, %s, %s, %s, 'ops2-seed', %s::jsonb
                    where not exists (
                        select 1 from project_notes
                        where project_id = %s and note_type = %s and title = %s
                    )
                    """,
                    (PROJECT_ID, note_type, note_type, body, _json({"seeded": True}), PROJECT_ID, note_type, note_type),
                )

            cur.execute(
                """
                insert into git_repositories (project_id, name, remote_url, default_branch, metadata)
                values (%s, 'AI-Operations-center', 'https://github.com/bluejay88/AI-Operations-center.git', 'master', %s::jsonb)
                on conflict (remote_url) do update set
                    project_id = excluded.project_id,
                    name = excluded.name,
                    updated_at = now()
                """,
                (PROJECT_ID, _json({"distribution": "brain-to-laptops"})),
            )

            for metric in _default_kpis():
                cur.execute(
                    """
                    insert into kpis (domain, name, value, unit, target, source, metadata)
                    values (%s, %s, %s, %s, %s, 'ops2-seed', %s::jsonb)
                    on conflict (metric_date, domain, name) do update set
                        value = excluded.value,
                        target = excluded.target,
                        source = excluded.source
                    """,
                    (
                        metric["domain"],
                        metric["name"],
                        metric["value"],
                        metric["unit"],
                        metric["target"],
                        _json({"widget": metric["widget"]}),
                    ),
                )

            for product in _default_products():
                cur.execute(
                    """
                    insert into products (name, product_type, status, price, recurring_price, owner_agent_id, metadata)
                    select %s, %s, %s, %s, %s, %s, %s::jsonb
                    where not exists (select 1 from products where name = %s)
                    """,
                    (
                        product["name"],
                        product["product_type"],
                        product["status"],
                        product["price"],
                        product["recurring_price"],
                        product["owner_agent_id"],
                        _json(product["metadata"]),
                        product["name"],
                    ),
                )

            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'seed_operations_2', 'project', %s, %s, %s::jsonb)
                """,
                (PROJECT_ID, "Seeded AI Operations Center 2.0 control plane.", _json({"source": "cli/api"})),
            )
        conn.commit()

    split = split_project(PROJECT_ID, "website", local=local)
    return {"project_id": PROJECT_ID, "seeded": True, "split": split}


def seed_improvement_backlog(local: bool = False) -> dict[str, Any]:
    priority_map = {"P0": 96, "P1": 82, "P2": 68}
    created = 0
    existing = 0
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for index, (title, category, priority_band) in enumerate(IMPROVEMENT_BACKLOG, start=1):
                agent_id = IMPROVEMENT_OWNERS[category]
                cur.execute(
                    """
                    insert into tasks (title, agent_id, category, description, priority, metadata)
                    select %s, %s, 'improvement', %s, %s, %s::jsonb
                    where not exists (
                        select 1 from tasks
                        where title = %s
                          and category = 'improvement'
                          and metadata->>'improvement_backlog' = 'ai-ops-100'
                    )
                    returning id
                    """,
                    (
                        f"Improvement {index:03d}: {title}",
                        agent_id,
                        (
                            f"{priority_band} {category} improvement. Produce implementation plan, validation criteria, "
                            "security impact, estimated effort, and a Brain approval request before high-impact changes."
                        ),
                        priority_map[priority_band],
                        _json(
                            {
                                "project_id": PROJECT_ID,
                                "improvement_backlog": "ai-ops-100",
                                "improvement_number": index,
                                "improvement_category": category,
                                "priority_band": priority_band,
                            }
                        ),
                        f"Improvement {index:03d}: {title}",
                    ),
                )
                if cur.fetchone():
                    created += 1
                else:
                    existing += 1
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'seed_improvement_backlog', 'project', %s, %s, %s::jsonb)
                """,
                (PROJECT_ID, f"Seeded AI Ops 100 improvement backlog: {created} created, {existing} existing.", _json({"created": created, "existing": existing})),
            )
        conn.commit()
    return {"created": created, "existing": existing, "total": len(IMPROVEMENT_BACKLOG)}


def seed_laptop_work_batches(tasks_per_laptop: int = 100, local: bool = False) -> dict[str, Any]:
    batch_id = datetime.now(UTC).strftime("laptop-work-%Y%m%d")
    result: dict[str, Any] = {"batch_id": batch_id, "machines": {}}
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for machine_id, spec in LAPTOP_WORKSTREAMS.items():
                created = 0
                existing = 0
                for index in range(1, tasks_per_laptop + 1):
                    theme = spec["themes"][(index - 1) % len(spec["themes"])]
                    agent_id = spec["agents"][(index - 1) % len(spec["agents"])]
                    wave = ((index - 1) // len(spec["themes"])) + 1
                    title = f"{machine_id} work {index:03d}: {theme}"
                    dedupe_key = f"{batch_id}:{machine_id}:{index:03d}:{theme.lower().replace(' ', '-')}"
                    cur.execute(
                        """
                        insert into tasks (title, agent_id, category, description, priority, metadata)
                        select %s, %s, 'laptop-workforce', %s, %s, %s::jsonb
                        where not exists (
                            select 1 from tasks
                            where metadata->>'dedupe_key' = %s
                        )
                        returning id
                        """,
                        (
                            title,
                            agent_id,
                            _laptop_work_description(machine_id, agent_id, theme, wave),
                            _laptop_work_priority(index),
                            _json(
                                {
                                    "project_id": PROJECT_ID,
                                    "batch_id": batch_id,
                                    "dedupe_key": dedupe_key,
                                    "machine_id": machine_id,
                                    "theme": theme,
                                    "wave": wave,
                                    "fallback": "git-api-ssh",
                                    "verification_required": True,
                                }
                            ),
                            dedupe_key,
                        ),
                    )
                    if cur.fetchone():
                        created += 1
                    else:
                        existing += 1
                _queue_laptop_instruction(cur, machine_id, batch_id, created, existing)
                result["machines"][machine_id] = {"created": created, "existing": existing}
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'seed_laptop_work_batches', 'batch', %s, %s, %s::jsonb)
                """,
                (batch_id, f"Seeded deduped laptop work batches for {len(LAPTOP_WORKSTREAMS)} laptops.", _json(result)),
            )
        conn.commit()
    return result


def _laptop_work_description(machine_id: str, agent_id: str, theme: str, wave: int) -> str:
    return (
        f"Wave {wave} task for {machine_id} owned by {agent_id}. Theme: {theme}. "
        "Before starting: pull GitHub master, run the laptop unblock audit, read the current speaker feed, "
        "and check for existing output with the same dedupe_key. Produce workstation updates with ETA, logs, "
        "errors, recommendations, and completion evidence. Request Brain approval before destructive, credential, "
        "financial, legal, deployment, or external-send actions."
    )


def _laptop_work_priority(index: int) -> int:
    if index <= 10:
        return 96
    if index <= 40:
        return 84
    if index <= 75:
        return 72
    return 60


def _queue_laptop_instruction(cur: Any, machine_id: str, batch_id: str, created: int, existing: int) -> None:
    cur.execute(
        """
        insert into speaker_messages (target_id, message_type, subject, body, priority, metadata)
        values (%s, 'work_batch', %s, %s, 92, %s::jsonb)
        """,
        (
            machine_id,
            f"New deduped work batch: {batch_id}",
            (
                f"{machine_id} has {created} new tasks and {existing} existing deduped tasks in batch {batch_id}. "
                "Run git pull origin master, run docker\\audit-laptop-unblock.ps1, check /speaker/feed, then claim work by assigned agent. "
                "Do not duplicate tasks: use metadata.dedupe_key and publish workstation updates after every meaningful checkpoint."
            ),
            _json({"batch_id": batch_id, "created": created, "existing": existing}),
        ),
    )


def _default_context_body(note_type: str, config: dict[str, Any]) -> str:
    if note_type == "Goals":
        return "Build a distributed AI operations factory that improves productivity and revenue toward $250k-$500k annual sales."
    if note_type == "Requirements":
        return "Brain PC orchestrates decisions, laptops execute specialized work, all changes flow through audit, approvals, reports, and portable import/export bundles."
    if note_type == "Decisions":
        return "Chat continuation is handled through structured project notes in the local knowledge base rather than direct automated access to ChatGPT conversations."
    if note_type == "Architecture":
        return "Domain-separated PostgreSQL, FastAPI control plane, Docker runtime, GitHub distribution, Tailscale/SSH connectivity, dashboard, listener/speaker bus, and approval gates."
    if note_type == "TODO":
        return "Bring all laptops worker-online, connect provider keys, enable backups, run benchmarks, then assign revenue-producing work by machine capacity."
    if note_type == "Progress Log":
        return "2.0 domain schema, operations config, approval bus, Phoenix briefing, readiness, and dashboard are being connected into one NOC view."
    if note_type == "Prompt History":
        return "Store prompts, exported project context, laptop instructions, and agent prompts here before assigning continuation work."
    return f"{note_type} entries will be imported, exported, reviewed, and reused by the Brain and laptop agents."


def _default_kpis() -> list[dict[str, Any]]:
    return [
        {"domain": "business", "name": "Revenue", "value": 0, "unit": "usd", "target": 500000, "widget": "business"},
        {"domain": "business", "name": "Monthly recurring revenue", "value": 0, "unit": "usd", "target": 41667, "widget": "business"},
        {"domain": "business", "name": "Leads", "value": 0, "unit": "count", "target": 2500, "widget": "business"},
        {"domain": "business", "name": "Sales", "value": 0, "unit": "count", "target": 250, "widget": "business"},
        {"domain": "business", "name": "Conversion rate", "value": 0, "unit": "percent", "target": 10, "widget": "business"},
        {"domain": "ai", "name": "Average response quality", "value": 82, "unit": "score", "target": 90, "widget": "ai_metrics"},
        {"domain": "security", "name": "Open critical events", "value": 0, "unit": "count", "target": 0, "widget": "security"},
    ]


def _default_products() -> list[dict[str, Any]]:
    return [
        {
            "name": "Small Business AI Website Maintenance",
            "product_type": "subscription_service",
            "status": "planning",
            "price": 750,
            "recurring_price": 299,
            "owner_agent_id": "website-builder",
            "metadata": {"sales_goal": "first revenue engine", "target": "local small businesses"},
        },
        {
            "name": "AI Prompt and Workflow Library",
            "product_type": "digital_product",
            "status": "idea",
            "price": 49,
            "recurring_price": 0,
            "owner_agent_id": "digital-products",
            "metadata": {"sales_goal": "passive product", "target": "operators and solo founders"},
        },
        {
            "name": "Business Forms and Automation Pack",
            "product_type": "digital_product",
            "status": "idea",
            "price": 79,
            "recurring_price": 0,
            "owner_agent_id": "business-manager",
            "metadata": {"sales_goal": "template revenue", "target": "small business owners"},
        },
    ]


def split_project(project_id: str, template: str = "website", local: bool = False) -> dict[str, Any]:
    config = load_operations_2()
    phases = config["project_split_template"][template]["phases"]
    created_tasks: list[int] = []

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for index, phase in enumerate(phases, start=1):
                cur.execute(
                    """
                    insert into project_phases (
                        project_id, phase_name, owner_agent_id, owner_machine_id,
                        status, progress, quality_gate, metadata
                    )
                    values (%s, %s, %s, %s, 'queued', 0, 'brain-review', %s::jsonb)
                    on conflict (project_id, phase_name) do update set
                        owner_agent_id = excluded.owner_agent_id,
                        owner_machine_id = excluded.owner_machine_id,
                        quality_gate = excluded.quality_gate,
                        metadata = project_phases.metadata || excluded.metadata,
                        updated_at = now()
                    """,
                    (
                        project_id,
                        phase["name"],
                        phase["owner_agent"],
                        phase["owner_machine"],
                        _json({"sequence": index, "template": template}),
                    ),
                )
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'split_project', 'project', %s, %s, %s::jsonb)
                """,
                (project_id, f"Split project into {len(phases)} {template} phases.", _json({"template": template})),
            )
        conn.commit()

    for phase in phases:
        task_id = create_task(
            title=f"{phase['name']}: {project_id}",
            agent_id=phase["owner_agent"],
            category="project-phase",
            description=(
                f"Execute the {phase['name']} phase for {project_id}. Read project context first, "
                "produce a work log, run the phase precheck rubric, and submit outputs to the Brain for review."
            ),
            priority=max(55, 96 - len(created_tasks) * 3),
            metadata={"project_id": project_id, "phase": phase["name"], "owner_machine": phase["owner_machine"]},
            local=local,
        )
        created_tasks.append(task_id)

    return {"project_id": project_id, "template": template, "phase_count": len(phases), "created_task_ids": created_tasks}


def project_context(project_id: str, local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from projects where id = %s", (project_id,))
            project = cur.fetchone()
            cur.execute(
                "select note_type, title, body, source, metadata, created_at from project_notes where project_id = %s order by note_type, created_at",
                (project_id,),
            )
            notes = cur.fetchall()
            cur.execute("select * from project_phases where project_id = %s order by id", (project_id,))
            phases = cur.fetchall()
            cur.execute("select * from git_repositories where project_id = %s order by id", (project_id,))
            repos = cur.fetchall()
    return {"project": project, "notes": notes, "phases": phases, "git_repositories": repos}


def noc_snapshot(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) filter (where status='active') as active_agents from agents")
            agents = dict(cur.fetchone())
            cur.execute(
                """
                select
                    count(*) filter (where status='running') as active_jobs,
                    count(*) filter (where status='queued') as queue_length,
                    count(*) filter (where status='completed') as completed_jobs
                from tasks
                """
            )
            jobs = dict(cur.fetchone())
            cur.execute("select * from projects order by updated_at desc limit 12")
            projects = cur.fetchall()
            cur.execute("select * from machine_status_current order by machine_id")
            machines = cur.fetchall()
            cur.execute(
                """
                select distinct on (machine_id) machine_id, cpu_score, memory_total_mb, memory_available_mb,
                    disk_free_mb, brain_latency_ms, docker_available, created_at
                from machine_benchmarks
                order by machine_id, created_at desc
                """
            )
            benchmarks = cur.fetchall()
            cur.execute("select domain, name, value, unit, target from kpis order by domain, name")
            kpis = cur.fetchall()
            cur.execute(
                """
                select
                    coalesce(sum(tokens_input + tokens_output), 0) as tokens_consumed,
                    coalesce(avg(inference_ms), 0) as average_inference_ms,
                    coalesce(avg(quality_score), 0) as average_quality,
                    count(*) filter (where success) as successes,
                    count(*) filter (where not success) as failures,
                    coalesce(sum(cost_estimate), 0) as cost_estimate
                from ai_metrics
                """
            )
            ai_metrics = dict(cur.fetchone())
            cur.execute("select * from security_events order by created_at desc limit 20")
            security_events = cur.fetchall()
            cur.execute("select count(*) as pending_approvals from approval_requests where status='pending'")
            approvals = dict(cur.fetchone())
            cur.execute("select * from reports order by created_at desc limit 8")
            reports = cur.fetchall()
            cur.execute("select * from backups order by created_at desc limit 5")
            backups = cur.fetchall()
            cur.execute("select * from notifications order by created_at desc limit 20")
            notifications = cur.fetchall()
            cur.execute("select * from workstation_updates order by created_at desc limit 30")
            updates = cur.fetchall()
            cur.execute(
                """
                select distinct on (machine_id) machine_id, agent_id, outcome, metrics, created_at
                from workstation_updates
                where update_type = 'laptop_unblock_audit'
                order by machine_id, created_at desc
                """
            )
            ssh_updates = cur.fetchall()
            cur.execute(
                """
                select distinct on (machine_id) *
                from device_telemetry
                order by machine_id, created_at desc
                """
            )
            telemetry = cur.fetchall()
            cur.execute("select * from resource_recommendations where status='open' order by priority desc, created_at desc limit 20")
            recommendations = cur.fetchall()
    ssh_status = _ssh_status_snapshot(ssh_updates)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "ai_workforce": {**agents, **jobs, "gpu_usage": None, "cpu_usage": _average_cpu(benchmarks), "memory_usage": _memory_usage(benchmarks)},
        "projects": projects,
        "business": kpis,
        "infrastructure": {
            "machines": machines,
            "benchmarks": benchmarks,
            "telemetry": telemetry,
            "ssh_status": ssh_status,
            "database_health": "ok",
            "backups": backups,
        },
        "ssh_status": ssh_status,
        "ai_metrics": ai_metrics,
        "security": {"events": security_events, "pending_approvals": approvals["pending_approvals"]},
        "reports": reports,
        "notifications": notifications,
        "collaboration": {"updates": updates, "recommendations": recommendations},
    }


def publish_workstation_update(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into workstation_updates (
                    machine_id, agent_id, project_id, task_id, update_type, priority, summary,
                    logs, metrics, errors, recommendations, estimated_completion_at, duration_ms,
                    resource_consumption, outcome, created_by
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s)
                returning *
                """,
                (
                    payload["machine_id"],
                    payload.get("agent_id"),
                    payload.get("project_id"),
                    payload.get("task_id"),
                    payload["update_type"],
                    payload.get("priority", 50),
                    payload["summary"],
                    payload.get("logs"),
                    _json(payload.get("metrics", {})),
                    _json(payload.get("errors", [])),
                    _json(payload.get("recommendations", [])),
                    payload.get("estimated_completion_at"),
                    payload.get("duration_ms"),
                    _json(payload.get("resource_consumption", {})),
                    payload.get("outcome"),
                    payload.get("created_by", "workstation"),
                ),
            )
            update = dict(cur.fetchone())
            cur.execute(
                """
                insert into work_logs (project_id, task_id, machine_id, agent_id, work_type, summary, status, quality_score, metadata)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    payload.get("project_id"),
                    payload.get("task_id"),
                    payload["machine_id"],
                    payload.get("agent_id"),
                    payload["update_type"],
                    payload["summary"],
                    payload.get("outcome", "published") or "published",
                    payload.get("quality_score"),
                    _json({"update_id": update["id"], "metrics": payload.get("metrics", {})}),
                ),
            )
            for recommendation in payload.get("recommendations", []):
                cur.execute(
                    """
                    insert into resource_recommendations (machine_id, recommendation_type, priority, summary, rationale, metadata)
                    values (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        payload["machine_id"],
                        recommendation.get("type", "workstation"),
                        recommendation.get("priority", payload.get("priority", 50)),
                        recommendation.get("summary", payload["summary"]),
                        recommendation.get("rationale", "Published by workstation update."),
                        _json({"update_id": update["id"], **recommendation.get("metadata", {})}),
                    ),
                )
            metrics = payload.get("metrics", {})
            if payload.get("update_type") == "laptop_unblock_audit" and metrics.get("ssh_noninteractive"):
                cur.execute(
                    """
                    update resource_recommendations
                    set status = 'resolved',
                        updated_at = now(),
                        metadata = metadata || %s::jsonb
                    where machine_id = %s
                      and recommendation_type = 'ssh_authentication'
                      and status = 'open'
                    """,
                    (
                        _json({"resolved_by_update_id": update["id"], "resolved_reason": "ssh_noninteractive_ready"}),
                        payload["machine_id"],
                    ),
                )
            if payload.get("update_type") == "laptop_unblock_audit" and metrics.get("brain_ssh_port") and not metrics.get("ssh_noninteractive"):
                cur.execute(
                    """
                    insert into resource_recommendations (machine_id, recommendation_type, priority, summary, rationale, metadata)
                    values (%s, 'ssh_authentication', 90, %s, %s, %s::jsonb)
                    """,
                    (
                        payload["machine_id"],
                        f"{payload['machine_id']} SSH network is unblocked but noninteractive login is not configured.",
                        "Complete one interactive login or install SSH keys so the Brain can run approved remote operations safely.",
                        _json({"update_id": update["id"], "metrics": metrics}),
                    ),
                )
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values (%s, 'publish_workstation_update', 'workstation_update', %s, %s, %s::jsonb)
                """,
                (
                    payload.get("agent_id") or payload["machine_id"],
                    str(update["id"]),
                    payload["summary"],
                    _json({"machine_id": payload["machine_id"], "task_id": payload.get("task_id")}),
                ),
            )
        conn.commit()
    return {"update": update}


def _ssh_status_snapshot(ssh_updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    statuses = []
    for row in ssh_updates:
        metrics = row.get("metrics") or {}
        port_ok = bool(metrics.get("brain_ssh_port"))
        auth_ok = bool(metrics.get("ssh_noninteractive"))
        if auth_ok:
            state = "noninteractive_ready"
            label = "SSH automation ready"
        elif port_ok:
            state = "interactive_login_required"
            label = "SSH network unblocked; login/key setup needed"
        else:
            state = "blocked"
            label = "SSH network blocked"
        statuses.append(
            {
                "machine_id": row.get("machine_id"),
                "agent_id": row.get("agent_id"),
                "state": state,
                "label": label,
                "brain_ssh_port": port_ok,
                "ssh_noninteractive": auth_ok,
                "brain_ssh_user": metrics.get("brain_ssh_user"),
                "tailscale": bool(metrics.get("tailscale")),
                "git": bool(metrics.get("git")),
                "brain_api": bool(metrics.get("brain_api")),
                "updated_at": row.get("created_at"),
            }
        )
    return statuses


def publish_device_telemetry(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into device_telemetry (
                    machine_id, device_name, hostname, operating_system, cpu, gpu, ram_mb,
                    storage_free_mb, battery_percent, current_user_name, network_status,
                    tailscale_status, current_ai_model, installed_models, active_projects,
                    current_tasks, idle_percentage, temperature_c, load_average, health_score, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    payload["machine_id"],
                    payload.get("device_name"),
                    payload.get("hostname"),
                    payload.get("operating_system"),
                    payload.get("cpu"),
                    payload.get("gpu"),
                    payload.get("ram_mb"),
                    payload.get("storage_free_mb"),
                    payload.get("battery_percent"),
                    payload.get("current_user"),
                    payload.get("network_status"),
                    payload.get("tailscale_status"),
                    payload.get("current_ai_model"),
                    _json(payload.get("installed_models", [])),
                    _json(payload.get("active_projects", [])),
                    _json(payload.get("current_tasks", [])),
                    payload.get("idle_percentage"),
                    payload.get("temperature_c"),
                    payload.get("load_average"),
                    payload.get("health_score"),
                    _json(payload.get("metadata", {})),
                ),
            )
            telemetry = dict(cur.fetchone())
            cur.execute(
                """
                update machine_status_current
                set status = coalesce(%s, status),
                    hostname = coalesce(%s, hostname),
                    metadata = metadata || %s::jsonb,
                    last_seen_at = now(),
                    updated_at = now()
                where machine_id = %s
                """,
                (
                    payload.get("network_status") or "online",
                    payload.get("hostname"),
                    _json({"latest_health_score": payload.get("health_score"), "latest_temperature_c": payload.get("temperature_c")}),
                    payload["machine_id"],
                ),
            )
            _create_health_recommendation(cur, payload)
        conn.commit()
    return {"telemetry": telemetry}


def _create_health_recommendation(cur: Any, payload: dict[str, Any]) -> None:
    temperature = payload.get("temperature_c")
    disk = payload.get("storage_free_mb")
    health = payload.get("health_score")
    if temperature is not None and float(temperature) >= 85:
        summary = f"{payload['machine_id']} temperature is high at {temperature}C."
        _insert_recommendation(cur, payload["machine_id"], "high_temperature", 95, summary, "Reduce workload or inspect cooling before assigning heavy jobs.")
    if disk is not None and float(disk) < 10240:
        summary = f"{payload['machine_id']} disk space is low."
        _insert_recommendation(cur, payload["machine_id"], "low_disk_space", 85, summary, "Free storage before build, Docker, or dataset workloads.")
    if health is not None and int(health) < 60:
        summary = f"{payload['machine_id']} health score is below routing threshold."
        _insert_recommendation(cur, payload["machine_id"], "health_score", 80, summary, "Route new work elsewhere until telemetry improves.")


def _insert_recommendation(cur: Any, machine_id: str, rec_type: str, priority: int, summary: str, rationale: str) -> None:
    cur.execute(
        """
        insert into resource_recommendations (machine_id, recommendation_type, priority, summary, rationale)
        values (%s, %s, %s, %s, %s)
        """,
        (machine_id, rec_type, priority, summary, rationale),
    )


def create_notification(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into notifications (
                    recipient, channel, subject, body, status, priority, category,
                    project_id, eta_at, actions, metadata
                )
                values (%s, %s, %s, %s, 'queued', %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                returning *
                """,
                (
                    payload["recipient"],
                    payload.get("channel", "dashboard"),
                    payload["subject"],
                    payload["body"],
                    payload.get("priority", 50),
                    payload.get("category", "general"),
                    payload.get("project_id"),
                    payload.get("eta_at"),
                    _json(payload.get("actions", ["acknowledge", "snooze"])),
                    _json(payload.get("metadata", {})),
                ),
            )
            notification = dict(cur.fetchone())
        conn.commit()
    return {"notification": notification}


def _average_cpu(benchmarks: list[dict[str, Any]]) -> float | None:
    scores = [float(row["cpu_score"]) for row in benchmarks if row.get("cpu_score") is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def _memory_usage(benchmarks: list[dict[str, Any]]) -> float | None:
    used = []
    for row in benchmarks:
        total = row.get("memory_total_mb")
        available = row.get("memory_available_mb")
        if total and available:
            used.append((float(total) - float(available)) / float(total) * 100)
    return round(sum(used) / len(used), 2) if used else None


def export_bundle(scope: str = "all", project_id: str = PROJECT_ID, local: bool = False) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "bundle_type": "ai_operations_center_2_export",
        "scope": scope,
        "project_id": project_id,
        "exported_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
        "data": {},
    }
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            tables = _export_tables(scope, project_id)
            for table, query, params in tables:
                cur.execute(query, params)
                bundle["data"][table] = cur.fetchall()
    return bundle


def import_bundle(bundle: dict[str, Any], local: bool = False) -> dict[str, Any]:
    if bundle.get("bundle_type") != "ai_operations_center_2_export":
        raise ValueError("Unsupported bundle_type")

    imported: dict[str, int] = {}
    data = bundle.get("data", {})
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for note in data.get("project_notes", []):
                cur.execute(
                    """
                    insert into project_notes (project_id, note_type, title, body, source, metadata)
                    values (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        note.get("project_id"),
                        note.get("note_type"),
                        note.get("title"),
                        note.get("body"),
                        note.get("source", "import-bundle"),
                        _json(note.get("metadata", {})),
                    ),
                )
                imported["project_notes"] = imported.get("project_notes", 0) + 1
            for log in data.get("work_logs", []):
                cur.execute(
                    """
                    insert into work_logs (project_id, task_id, machine_id, agent_id, work_type, summary, status, quality_score, metadata)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        log.get("project_id"),
                        log.get("task_id"),
                        log.get("machine_id"),
                        log.get("agent_id"),
                        log.get("work_type", "imported"),
                        log.get("summary"),
                        log.get("status", "imported"),
                        log.get("quality_score"),
                        _json(log.get("metadata", {})),
                    ),
                )
                imported["work_logs"] = imported.get("work_logs", 0) + 1
            for document in data.get("documents", []):
                cur.execute(
                    """
                    insert into documents (project_id, title, document_type, path, status, metadata)
                    values (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        document.get("project_id"),
                        document.get("title"),
                        document.get("document_type", "imported"),
                        document.get("path"),
                        document.get("status", "imported"),
                        _json(document.get("metadata", {})),
                    ),
                )
                imported["documents"] = imported.get("documents", 0) + 1
            for prompt in data.get("prompts", []):
                cur.execute(
                    """
                    insert into prompts (name, owner_agent_id, purpose, prompt_text, version, status, metadata)
                    values (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    on conflict (name, version) do update set
                        owner_agent_id = excluded.owner_agent_id,
                        purpose = excluded.purpose,
                        prompt_text = excluded.prompt_text,
                        status = excluded.status,
                        metadata = excluded.metadata,
                        updated_at = now()
                    """,
                    (
                        prompt.get("name"),
                        prompt.get("owner_agent_id"),
                        prompt.get("purpose", "imported"),
                        prompt.get("prompt_text", ""),
                        prompt.get("version", 1),
                        prompt.get("status", "active"),
                        _json(prompt.get("metadata", {})),
                    ),
                )
                imported["prompts"] = imported.get("prompts", 0) + 1
            for report in data.get("reports", []):
                cur.execute(
                    "insert into reports (report_type, title, body) values (%s, %s, %s)",
                    (report.get("report_type", "imported"), report.get("title", "Imported report"), report.get("body", "")),
                )
                imported["reports"] = imported.get("reports", 0) + 1
            for kpi in data.get("kpis", []):
                cur.execute(
                    """
                    insert into kpis (metric_date, domain, name, value, unit, target, source, metadata)
                    values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    on conflict (metric_date, domain, name) do update set
                        value = excluded.value,
                        unit = excluded.unit,
                        target = excluded.target,
                        source = excluded.source,
                        metadata = excluded.metadata
                    """,
                    (
                        kpi.get("metric_date"),
                        kpi.get("domain"),
                        kpi.get("name"),
                        kpi.get("value", 0),
                        kpi.get("unit", "count"),
                        kpi.get("target"),
                        kpi.get("source", "import-bundle"),
                        _json(kpi.get("metadata", {})),
                    ),
                )
                imported["kpis"] = imported.get("kpis", 0) + 1
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'import_bundle', 'bundle', %s, %s, %s::jsonb)
                """,
                (bundle.get("project_id"), "Imported AI Operations Center bundle.", _json({"scope": bundle.get("scope"), "counts": imported})),
            )
        conn.commit()
    return {"imported": imported}


def _export_tables(scope: str, project_id: str) -> list[tuple[str, str, tuple[Any, ...]]]:
    project_tables = [
        ("projects", "select * from projects where id = %s", (project_id,)),
        ("project_phases", "select * from project_phases where project_id = %s order by id", (project_id,)),
        ("project_notes", "select * from project_notes where project_id = %s order by id", (project_id,)),
        ("documents", "select * from documents where project_id = %s order by id", (project_id,)),
        ("git_repositories", "select * from git_repositories where project_id = %s order by id", (project_id,)),
        ("work_logs", "select * from work_logs where project_id = %s order by id", (project_id,)),
        ("reports", "select * from reports order by created_at desc limit 50", ()),
    ]
    ops_tables = [
        ("machines", "select * from machines order by id", ()),
        ("agents", "select * from agents order by id", ()),
        ("tasks", "select * from tasks order by id desc limit 500", ()),
        ("kpis", "select * from kpis order by metric_date desc, domain, name", ()),
        ("prompts", "select * from prompts order by name, version", ()),
        ("products", "select * from products order by id", ()),
        ("notifications", "select * from notifications order by id desc limit 500", ()),
        ("remote_operation_requests", "select * from remote_operation_requests order by id desc limit 500", ()),
        ("resource_recommendations", "select * from resource_recommendations order by id desc limit 500", ()),
        ("workstation_updates", "select * from workstation_updates order by id desc limit 500", ()),
        ("device_telemetry", "select * from device_telemetry order by id desc limit 500", ()),
        ("security_events", "select * from security_events order by id desc limit 200", ()),
        ("audit_logs", "select * from audit_logs order by id desc limit 500", ()),
    ]
    if scope == "project":
        return project_tables
    if scope == "ops":
        return ops_tables
    return project_tables + ops_tables
