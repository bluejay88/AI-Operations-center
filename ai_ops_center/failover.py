from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import connect


BATTERY_CRITICAL_PERCENT = 5
STALE_AFTER_MINUTES = 3

FALLBACK_BY_AGENT = {
    "programmer": "code-reviewer",
    "code-reviewer": "programmer",
    "website-builder": "programmer",
    "research-lead": "grant-scout",
    "grant-scout": "research-lead",
    "resale-scout": "research-lead",
    "gaming-intel": "research-lead",
    "business-manager": "project-coordinator",
    "finance-manager": "project-coordinator",
    "social-media": "content-engine",
    "lead-generation": "research-lead",
    "marketing-agent": "content-engine",
    "digital-products": "content-engine",
}

FALLBACK_BY_MACHINE = {
    "dev-laptop": ["brain-gaming-pc", "business-laptop", "research-laptop"],
    "research-laptop": ["brain-gaming-pc", "business-laptop", "dev-laptop"],
    "business-laptop": ["brain-gaming-pc", "research-laptop", "dev-laptop"],
    "brain-gaming-pc": ["dev-laptop", "research-laptop", "business-laptop"],
}


def failover_recommendation(machine_id: str, battery_percent: float | None, state: str | None = None) -> dict[str, Any]:
    state = state or "online"
    battery = float(battery_percent) if battery_percent is not None else None
    critical_battery = battery is not None and battery <= BATTERY_CRITICAL_PERCENT
    unavailable = state in {"offline", "worker_stale", "reachable_worker_stale", "blocked"}
    should_failover = critical_battery or unavailable
    reason = "healthy"
    if critical_battery:
        reason = f"battery_at_or_below_{BATTERY_CRITICAL_PERCENT}_percent"
    elif unavailable:
        reason = f"machine_state_{state}"
    return {
        "machine_id": machine_id,
        "should_failover": should_failover,
        "reason": reason,
        "battery_percent": battery,
        "state": state,
    }


def evaluate_failover(
    machine_id: str,
    battery_percent: float | None = None,
    state: str | None = None,
    trigger: str = "manual",
    local: bool = False,
) -> dict[str, Any]:
    recommendation = failover_recommendation(machine_id, battery_percent, state)
    if not recommendation["should_failover"]:
        return {"triggered": False, "recommendation": recommendation, "reassigned": []}

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select t.*, a.machine_id as assigned_machine_id
                from tasks t
                join agents a on a.id = t.agent_id
                where coalesce(t.execution_machine_id, a.machine_id) = %s
                  and t.status = 'queued'
                order by
                    case t.status when 'running' then 0 else 1 end,
                    t.priority desc,
                    t.updated_at asc
                for update of t skip locked
                limit 50
                """,
                (machine_id,),
            )
            tasks = [dict(row) for row in cur.fetchall()]

            reassigned = []
            for task in tasks:
                fallback_agent = _choose_fallback_agent(cur, machine_id, task["agent_id"])
                if not fallback_agent:
                    continue
                cur.execute("select machine_id from agents where id = %s", (fallback_agent,))
                fallback_machine = cur.fetchone()["machine_id"]
                cur.execute(
                    """
                    update tasks
                    set agent_id = %s,
                        execution_machine_id = %s,
                        status = 'queued',
                        metadata = metadata || %s::jsonb,
                        updated_at = now()
                    where id = %s
                    returning id, title, agent_id, status
                    """,
                    (
                        fallback_agent,
                        fallback_machine,
                        json.dumps(
                            {
                                "failover": {
                                    "from_machine": machine_id,
                                    "from_agent": task["agent_id"],
                                    "to_agent": fallback_agent,
                                    "reason": recommendation["reason"],
                                    "trigger": trigger,
                                    "handoff_at": datetime.now(UTC).isoformat(),
                                }
                            }
                        ),
                        task["id"],
                    ),
                )
                updated = dict(cur.fetchone())
                cur.execute(
                    """
                    insert into task_events (task_id, event_type, message)
                    values (%s, 'failover_reassigned', %s)
                    """,
                    (
                        task["id"],
                        f"Brain reassigned from {task['agent_id']} on {machine_id} to {fallback_agent}; reason={recommendation['reason']}.",
                    ),
                )
                reassigned.append(
                    {
                        "task_id": updated["id"],
                        "title": updated["title"],
                        "from_agent": task["agent_id"],
                        "to_agent": fallback_agent,
                        "reason": recommendation["reason"],
                    }
                )

            if reassigned:
                _record_failover_artifacts(cur, machine_id, recommendation, reassigned)
        conn.commit()

    return {"triggered": True, "recommendation": recommendation, "reassigned": reassigned}


def evaluate_stale_workers(local: bool = False, stale_after_minutes: int = STALE_AFTER_MINUTES) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
    results = []
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select machine_id, status, last_seen_at
                from machine_status_current
                where machine_id != 'brain-gaming-pc'
                  and (status in ('offline', 'blocked') or last_seen_at < %s)
                order by last_seen_at nulls first
                """,
                (cutoff,),
            )
            machines = [dict(row) for row in cur.fetchall()]
    for machine in machines:
        state = "worker_stale" if machine.get("last_seen_at") and machine["last_seen_at"] < cutoff else machine.get("status", "offline")
        results.append(evaluate_failover(machine["machine_id"], state=state, trigger="stale-worker-watch", local=local))
    return {"evaluated": len(results), "results": results}


def _choose_fallback_agent(cur: Any, source_machine_id: str, source_agent_id: str) -> str | None:
    preferred = FALLBACK_BY_AGENT.get(source_agent_id)
    candidates = []
    if preferred:
        candidates.append(preferred)
    for machine_id in FALLBACK_BY_MACHINE.get(source_machine_id, ["brain-gaming-pc"]):
        cur.execute(
            """
            select id
            from agents
            where machine_id = %s
              and status = 'active'
            order by
                case id
                    when 'orchestrator' then 0
                    when 'project-coordinator' then 1
                    when 'programmer' then 2
                    when 'research-lead' then 3
                    else 4
                end,
                id
            limit 3
            """,
            (machine_id,),
        )
        candidates.extend(row["id"] for row in cur.fetchall())
    for agent_id in candidates:
        cur.execute(
            """
            select a.id
            from agents a
            join machine_status_current ms on ms.machine_id = a.machine_id
            where a.id = %s and a.status = 'active'
              and a.machine_id <> %s
              and ms.status = 'online'
              and ms.last_seen_at >= now() - interval '60 seconds'
            """,
            (agent_id, source_machine_id),
        )
        if cur.fetchone():
            return agent_id
    return None


def _record_failover_artifacts(cur: Any, machine_id: str, recommendation: dict[str, Any], reassigned: list[dict[str, Any]]) -> None:
    summary = f"{machine_id} failover triggered: {recommendation['reason']}."
    body = (
        f"{summary}\n"
        f"Battery: {recommendation.get('battery_percent')} / State: {recommendation.get('state')}.\n"
        f"Reassigned tasks: {len(reassigned)}.\n"
        "Brain should preserve handoff notes, require a git savepoint at critical battery, and keep the factory moving."
    )
    cur.execute(
        """
        insert into project_notes (project_id, note_type, title, body, source, metadata)
        values ('ai-operations-center-2', 'Failover', %s, %s, 'brain-failover', %s::jsonb)
        """,
        (summary, body, json.dumps({"machine_id": machine_id, "reassigned": reassigned, "recommendation": recommendation})),
    )
    cur.execute(
        """
        insert into notifications (recipient, channel, subject, body, status, priority, category, actions, metadata)
        values ('brain-gaming-pc', 'dashboard', %s, %s, 'queued', 98, 'failover', %s::jsonb, %s::jsonb)
        """,
        (summary, body, json.dumps(["acknowledge", "review", "assign"]), json.dumps({"machine_id": machine_id, "reassigned": reassigned})),
    )
    cur.execute(
        """
        insert into speaker_messages (target_id, message_type, subject, body, priority, metadata)
        values (%s, 'failover_savepoint', %s, %s, 99, %s::jsonb)
        """,
        (
            machine_id,
            "Critical failover savepoint required",
            "Battery/offline policy triggered. Save all work, commit/push if safe, publish handoff notes, and stop taking new work until stable.",
            json.dumps({"machine_id": machine_id, "recommendation": recommendation}),
        ),
    )
    cur.execute(
        """
        insert into remote_operation_requests (machine_id, operation_type, command_summary, approval_policy, status, priority, metadata)
        values (%s, 'git_safepoint', %s, 'preapproved', 'queued', 99, %s::jsonb)
        """,
        (
            machine_id,
            "At 5% battery or failover: git status, save artifacts, commit safe local work, push if credentials/network are available, then publish handoff.",
            json.dumps({"reason": recommendation["reason"], "requires_non_destructive_only": True}),
        ),
    )
    cur.execute(
        """
        insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
        values ('brain-gaming-pc', 'failover_triggered', 'machine', %s, %s, %s::jsonb)
        """,
        (machine_id, summary, json.dumps({"reassigned": reassigned, "recommendation": recommendation})),
    )
