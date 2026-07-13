from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .integrations import integration_status
from .ops2 import noc_snapshot
from .readiness import readiness_snapshot
from .reports import generate_report
from .tasks import task_snapshot
from .db import connect


def codex_handoff_packet(
    prompt: str = "Analyze the AI Operations Center state and decide the next best implementation steps.",
    local: bool = False,
) -> dict[str, Any]:
    readiness = readiness_snapshot(local=local)
    noc = noc_snapshot(local=local)
    tasks = task_snapshot(limit=25, local=local)
    recent = _recent_operational_context(local=local)
    recommendations = _recommendations(readiness, noc, tasks, recent)
    codex_prompt = _build_prompt(prompt, readiness, noc, tasks, recent, recommendations, local=local)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "prompt": prompt,
        "summary": {
            "machines": [
                {
                    "id": machine["id"],
                    "role": machine["role"],
                    "state": machine["state"],
                    "task_counts": machine.get("task_counts", {}),
                    "last_seen": machine.get("last_seen"),
                }
                for machine in readiness.get("machines", [])
            ],
            "ai_workforce": noc.get("ai_workforce", {}),
            "providers": integration_status().get("providers", []),
        },
        "recent": recent,
        "recommendations": recommendations,
        "codex_prompt": codex_prompt,
    }


def _recent_operational_context(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, provider, purpose, status, left(coalesce(response_body, ''), 900) as response_body, created_at, completed_at
                from integration_runs
                order by created_at desc
                limit 12
                """
            )
            integrations = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select id, source_type, source_id, event_type, subject, left(body, 700) as body, priority, created_at
                from listener_events
                order by created_at desc
                limit 12
                """
            )
            events = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select id, machine_id, requested_by, operation_type, command_summary, approval_policy, status, priority, created_at
                from remote_operation_requests
                order by created_at desc
                limit 12
                """
            )
            remote_ops = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select id, title, request_type, requester_machine_id, requester_agent_id, risk_level, status, left(summary, 700) as summary, created_at
                from approval_requests
                order by created_at desc
                limit 12
                """
            )
            approvals = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select id, machine_id, agent_id, update_type, priority, summary, outcome, created_at
                from workstation_updates
                order by created_at desc
                limit 12
                """
            )
            updates = [dict(row) for row in cur.fetchall()]
    return {
        "integration_runs": integrations,
        "listener_events": events,
        "remote_operations": remote_ops,
        "approval_requests": approvals,
        "workstation_updates": updates,
    }


def _recommendations(readiness: dict[str, Any], noc: dict[str, Any], tasks: list[dict[str, Any]], recent: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    machines = readiness.get("machines", [])
    for machine in machines:
        counts = machine.get("task_counts", {})
        if machine.get("state") != "online":
            recs.append(f"Bring {machine['id']} back to online state before assigning heavy work.")
        if counts.get("queued", 0) > 100 and counts.get("running", 0) == 0:
            recs.append(f"Start or repair worker execution on {machine['id']}; it has {counts.get('queued')} queued tasks and none running.")
        if any(c.get("channel") == "ssh-22-brain-to-laptop" and c.get("status") == "blocked" for c in machine.get("connections", [])):
            recs.append(f"Enable inbound OpenSSH on {machine['id']} over Tailscale if Brain-to-laptop command execution is required.")
    providers = integration_status().get("providers", [])
    for provider in providers:
        if provider["id"] in {"claude", "gemini"} and provider.get("configured"):
            recs.append(f"Review {provider['label']} health: configured but may need model/quota repair before production routing.")
    if (noc.get("ai_workforce") or {}).get("queue_length", 0) > 400:
        recs.append("Prioritize queue-draining automation and duplicate-task cleanup before seeding more large batches.")
    if not recs:
        recs.append("System is stable enough for the next feature increment: improve dashboard controls and automate approved worker loops.")
    return recs[:10]


def _build_prompt(
    prompt: str,
    readiness: dict[str, Any],
    noc: dict[str, Any],
    tasks: list[dict[str, Any]],
    recent: dict[str, Any],
    recommendations: list[str],
    local: bool,
) -> str:
    lines = [
        "# Codex Handoff Packet",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "You are Codex working inside the AI Operations Center repository. Analyze the state below, choose the next concrete implementation steps, make code changes if needed, run tests/audits, and report blockers honestly.",
        "",
        f"Operator prompt: {prompt}",
        "",
        "## Current Report",
        generate_report("hourly", local=local),
        "",
        "## Machine Readiness",
    ]
    for machine in readiness.get("machines", []):
        counts = machine.get("task_counts", {})
        lines.append(f"- {machine['id']} ({machine['role']}): {machine['state']}; queued={counts.get('queued', 0)} running={counts.get('running', 0)} completed={counts.get('completed', 0)}")
    lines.extend(["", "## Highest Priority Tasks"])
    for task in tasks[:12]:
        lines.append(f"- #{task['id']} P{task['priority']} [{task['status']}] {task['title']} -> {task['machine_id']}/{task['agent_id']}")
    lines.extend(["", "## Recent Integration Runs"])
    for run in recent["integration_runs"][:8]:
        lines.append(f"- #{run['id']} {run['provider']} {run['purpose']}: {run['status']} {run.get('response_body') or ''}")
    lines.extend(["", "## Recent Remote Ops / Approvals"])
    for op in recent["remote_operations"][:6]:
        lines.append(f"- remote #{op['id']} {op['machine_id']} {op['operation_type']} {op['status']} policy={op['approval_policy']}: {op['command_summary']}")
    for approval in recent["approval_requests"][:6]:
        lines.append(f"- approval #{approval['id']} {approval['status']} {approval['risk_level']}: {approval['title']}")
    lines.extend(["", "## Recommended Next Steps"])
    lines.extend(f"- {rec}" for rec in recommendations)
    lines.extend(["", "## Required Output From Codex", "- Files changed", "- Tests/audits run", "- Deployment or push status", "- Remaining blockers", "- Next commands for laptops if any"])
    return "\n".join(lines)
