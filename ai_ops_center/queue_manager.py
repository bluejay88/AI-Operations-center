from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import load_machines
from .db import connect


HEARTBEAT_STALE_SECONDS = 60
LEASE_SECONDS = 120
LEGACY_STALL_SECONDS = 600
QUEUE_GRACE_SECONDS = 15
MAX_MOVES_PER_SWEEP = 50
STEWARD_LOCK_ID = 2_026_071_301

APPROVAL_HOLD_STATES = {"pending_approval", "approval_required", "blocked"}


def retry_delay_seconds(attempt_count: int) -> int:
    """Bounded exponential retry delay used after an abandoned/failed claim."""
    return min(300, max(5, 5 * (2 ** max(0, int(attempt_count) - 1))))


def task_is_automatic_eligible(metadata: dict[str, Any] | None) -> bool:
    metadata = metadata or {}
    queue_state = str(metadata.get("queue_state") or "").strip().lower()
    if queue_state in APPROVAL_HOLD_STATES:
        return False
    requires_approval = str(metadata.get("requires_approval") or "false").strip().lower() in {"1", "true", "yes"}
    approval_status = str(metadata.get("approval_status") or "").strip().lower()
    if requires_approval and approval_status not in {"approved", "deployed"}:
        return False
    return not bool(metadata.get("no_failover") or metadata.get("pinned_machine") or metadata.get("requires_local_resources"))


def rank_fallback_targets(loads: dict[str, dict[str, int]], source_machine_id: str) -> list[str]:
    candidates = [machine_id for machine_id in loads if machine_id != source_machine_id]
    return sorted(
        candidates,
        key=lambda machine_id: (
            loads[machine_id]["running"] > 0,
            (loads[machine_id]["running"] + loads[machine_id]["queued"]) / max(1, loads[machine_id]["capacity"]),
            machine_id,
        ),
    )


def queue_health(local: bool = False, now: datetime | None = None) -> dict[str, Any]:
    observed_at = now or datetime.now(UTC)
    heartbeat_cutoff = observed_at - timedelta(seconds=HEARTBEAT_STALE_SECONDS)
    legacy_cutoff = observed_at - timedelta(seconds=LEGACY_STALL_SECONDS)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, count(*) as count
                from tasks
                group by status
                """
            )
            counts = {str(row["status"]): int(row["count"]) for row in cur.fetchall()}
            cur.execute(
                """
                select
                    extract(epoch from (now() - min(created_at))) as oldest_queue_age_seconds,
                    count(*) filter (where next_attempt_at is not null and next_attempt_at > now()) as retry_waiting
                from tasks
                where status = 'queued'
                """
            )
            queue_row = dict(cur.fetchone() or {})
            cur.execute(
                """
                select count(*) as count
                from tasks
                where status = 'running'
                  and (
                    (claim_token is not null and lease_expires_at < now())
                    or (claim_token is null and updated_at < %s)
                  )
                """,
                (legacy_cutoff,),
            )
            stalled = int(cur.fetchone()["count"])
            cur.execute(
                """
                select m.id, m.capacity_weight,
                       count(t.id) filter (where t.status = 'running') as running,
                       count(t.id) filter (where t.status = 'queued') as queued
                from machines m
                join machine_status_current ms on ms.machine_id = m.id
                left join tasks t on t.execution_machine_id = m.id
                where ms.status = 'online' and ms.last_seen_at >= %s
                group by m.id, m.capacity_weight
                order by m.id
                """,
                (heartbeat_cutoff,),
            )
            machine_load = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select count(*) as count
                from tasks
                where status = 'completed' and completed_at >= now() - interval '5 minutes'
                """
            )
            completed_5m = int(cur.fetchone()["count"])

    queued = int(counts.get("queued", 0))
    running = int(counts.get("running", 0))
    rate_per_minute = completed_5m / 5.0
    idle_healthy = [
        str(row["id"])
        for row in machine_load
        if int(row.get("running") or 0) == 0 and int(row.get("queued") or 0) == 0
    ]
    drain_eta_minutes = round(queued / rate_per_minute, 1) if queued and rate_per_minute > 0 else (0.0 if queued == 0 else None)
    return {
        "generated_at": observed_at.isoformat(),
        "queued": queued,
        "running": running,
        "stalled_running": stalled,
        "retry_waiting": int(queue_row.get("retry_waiting") or 0),
        "oldest_queue_age_seconds": float(queue_row.get("oldest_queue_age_seconds") or 0),
        "completed_last_5_minutes": completed_5m,
        "throughput_per_minute": round(rate_per_minute, 2),
        "estimated_drain_minutes": drain_eta_minutes,
        "healthy_machines": len(machine_load),
        "idle_healthy_machines": idle_healthy,
        "machine_load": machine_load,
        "contract": {
            "version": 1,
            "claims_are_leased": True,
            "completion_is_fenced": True,
            "automatic_approval_holds": True,
            "invariants": {
                "no_stalled_running_tasks": stalled == 0,
                "no_healthy_machine_idle_while_backlogged": queued == 0 or not idle_healthy,
            },
        },
    }


def steward_queue(
    local: bool = False,
    max_moves: int = MAX_MOVES_PER_SWEEP,
    now: datetime | None = None,
) -> dict[str, Any]:
    if max_moves < 1 or max_moves > 500:
        raise ValueError("max_moves must be between 1 and 500")
    observed_at = now or datetime.now(UTC)
    heartbeat_cutoff = observed_at - timedelta(seconds=HEARTBEAT_STALE_SECONDS)
    legacy_cutoff = observed_at - timedelta(seconds=LEGACY_STALL_SECONDS)
    queue_cutoff = observed_at - timedelta(seconds=QUEUE_GRACE_SECONDS)
    employed = {
        str(machine["id"])
        for machine in load_machines()
        if str(machine.get("workforce_status") or "employed") == "employed"
    }
    result: dict[str, Any] = {
        "status": "completed",
        "recovered": 0,
        "dead_lettered": 0,
        "rerouted": 0,
        "held": 0,
        "moves": [],
    }

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_try_advisory_xact_lock(%s) as acquired", (STEWARD_LOCK_ID,))
            if not bool(cur.fetchone()["acquired"]):
                return {**result, "status": "skipped_locked"}

            cur.execute(
                """
                update tasks t
                set execution_machine_id = a.machine_id
                from agents a
                where t.agent_id = a.id and t.execution_machine_id is null
                """
            )

            cur.execute(
                """
                select id, attempt_count, max_attempts, claimed_by_machine
                from tasks
                where status = 'running'
                  and (
                    (claim_token is not null and lease_expires_at < %s)
                    or (claim_token is null and updated_at < %s)
                  )
                order by coalesce(lease_expires_at, updated_at), priority desc
                for update skip locked
                limit %s
                """,
                (observed_at, legacy_cutoff, max_moves),
            )
            expired = [dict(row) for row in cur.fetchall()]
            for task in expired:
                attempts = int(task.get("attempt_count") or 0)
                if attempts >= int(task.get("max_attempts") or 3):
                    cur.execute(
                        """
                        update tasks
                        set status = 'failed', last_error = 'claim lease expired after maximum attempts',
                            claim_token = null, claimed_by_machine = null, lease_expires_at = null,
                            updated_at = %s
                        where id = %s and status = 'running'
                        """,
                        (observed_at, task["id"]),
                    )
                    event_type = "dead_lettered"
                    result["dead_lettered"] += cur.rowcount
                else:
                    retry_at = observed_at + timedelta(seconds=retry_delay_seconds(attempts))
                    cur.execute(
                        """
                        update tasks
                        set status = 'queued', started_at = null, claim_token = null,
                            claimed_by_machine = null, lease_expires_at = null,
                            next_attempt_at = %s, last_error = 'claim lease expired', updated_at = %s
                        where id = %s and status = 'running'
                        """,
                        (retry_at, observed_at, task["id"]),
                    )
                    event_type = "lease_recovered"
                    result["recovered"] += cur.rowcount
                if cur.rowcount:
                    cur.execute(
                        "insert into task_events (task_id, event_type, message) values (%s, %s, %s)",
                        (task["id"], event_type, f"Queue steward {event_type}; previous_machine={task.get('claimed_by_machine')}."),
                    )

            cur.execute(
                """
                select m.id, greatest(1, m.capacity_weight) as capacity_weight,
                       count(t.id) filter (where t.status = 'running') as running,
                       count(t.id) filter (where t.status = 'queued') as queued
                from machines m
                join machine_status_current ms on ms.machine_id = m.id
                left join tasks t on t.execution_machine_id = m.id and t.status in ('queued', 'running')
                where ms.status = 'online' and ms.last_seen_at >= %s
                group by m.id, m.capacity_weight
                order by m.id
                """,
                (heartbeat_cutoff,),
            )
            loads = {
                str(row["id"]): {
                    "capacity": int(row["capacity_weight"]),
                    "running": int(row["running"]),
                    "queued": int(row["queued"]),
                }
                for row in cur.fetchall()
                if str(row["id"]) in employed
            }
            healthy = set(loads)
            if healthy:
                cur.execute(
                    """
                    select t.id, t.title, t.agent_id, t.category, t.metadata,
                           coalesce(t.execution_machine_id, a.machine_id) as source_machine_id,
                           t.assignment_generation
                    from tasks t
                    join agents a on a.id = t.agent_id
                    where t.status = 'queued'
                      and t.updated_at <= %s
                      and (t.next_attempt_at is null or t.next_attempt_at <= %s)
                    order by
                      (t.priority + least(20, floor(extract(epoch from (%s - t.created_at)) / 3600))) desc,
                      t.created_at asc
                    for update of t skip locked
                    limit %s
                    """,
                    (queue_cutoff, observed_at, observed_at, max_moves * 4),
                )
                queued_tasks = [dict(row) for row in cur.fetchall()]

                for task in queued_tasks:
                    metadata = task.get("metadata") or {}
                    if not task_is_automatic_eligible(metadata):
                        result["held"] += 1
                        continue
                    source = str(task.get("source_machine_id") or "")
                    targets = rank_fallback_targets(loads, source)
                    if not targets:
                        continue
                    target = targets[0]
                    target_load = loads[target]["running"] + loads[target]["queued"]
                    source_load = loads.get(source, {"running": 0, "queued": 0})
                    source_total = source_load["running"] + source_load["queued"]
                    source_unhealthy = source not in healthy
                    target_has_room = target_load < loads[target]["capacity"]
                    balances_backlog = source_total > target_load + 1
                    if not source_unhealthy and not (target_has_room and balances_backlog):
                        continue

                    cur.execute(
                        """
                        select id
                        from agents
                        where machine_id = %s and status = 'active'
                        order by case when category = %s then 0 else 1 end, id
                        limit 1
                        """,
                        (target, task["category"]),
                    )
                    target_agent_row = cur.fetchone()
                    if not target_agent_row:
                        continue
                    target_agent = str(target_agent_row["id"])
                    generation = int(task.get("assignment_generation") or 0) + 1
                    routing = {
                        "original_agent_id": metadata.get("queue_routing", {}).get("original_agent_id", task["agent_id"]),
                        "from_machine": source,
                        "to_machine": target,
                        "from_agent": task["agent_id"],
                        "to_agent": target_agent,
                        "reason": "source_unhealthy" if source_unhealthy else "capacity_balance",
                        "generation": generation,
                        "routed_at": observed_at.isoformat(),
                    }
                    cur.execute(
                        """
                        update tasks
                        set execution_machine_id = %s, agent_id = %s,
                            assignment_generation = %s,
                            metadata = metadata || %s::jsonb,
                            updated_at = %s
                        where id = %s and status = 'queued'
                        """,
                        (target, target_agent, generation, json.dumps({"queue_routing": routing}), observed_at, task["id"]),
                    )
                    if not cur.rowcount:
                        continue
                    cur.execute(
                        "insert into task_events (task_id, event_type, message) values (%s, 'queue_rerouted', %s)",
                        (task["id"], f"Queue steward moved work {source}->{target}; generation={generation}."),
                    )
                    if source in loads:
                        loads[source]["queued"] = max(0, loads[source]["queued"] - 1)
                    loads[target]["queued"] += 1
                    result["rerouted"] += 1
                    result["moves"].append({"task_id": task["id"], **routing})
                    if result["rerouted"] >= max_moves:
                        break
        conn.commit()

    result["queue_health"] = queue_health(local=local, now=observed_at)
    return result
