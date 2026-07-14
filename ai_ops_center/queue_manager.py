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
QUEUE_STARVATION_SECONDS = 60
MAX_MOVES_PER_SWEEP = 50
STEWARD_LOCK_ID = 2_026_071_301

APPROVAL_HOLD_STATES = {"pending_approval", "approval_required", "blocked"}
TERMINAL_TASK_STATES = {"completed", "failed", "cancelled"}


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


def task_is_claim_eligible(metadata: dict[str, Any] | None) -> bool:
    metadata = metadata or {}
    queue_state = str(metadata.get("queue_state") or "").strip().lower()
    if queue_state in APPROVAL_HOLD_STATES:
        return False
    requires_approval = str(metadata.get("requires_approval") or "false").strip().lower() in {"1", "true", "yes"}
    approval_status = str(metadata.get("approval_status") or "").strip().lower()
    return not requires_approval or approval_status in {"approved", "deployed"}


def derive_parent_status(task_statuses: list[str]) -> str:
    """Project a group of worker tasks onto its durable parent request."""
    states = {str(status).strip().lower() for status in task_statuses if status}
    if not states:
        return "queued"
    if states == {"completed"}:
        return "completed"
    if states <= TERMINAL_TASK_STATES:
        return "failed" if states & {"failed", "cancelled"} else "completed"
    if "running" in states:
        return "running"
    return "queued"


def queued_hold_reason(
    metadata: dict[str, Any] | None,
    *,
    retry_at: datetime | None = None,
    now: datetime | None = None,
    source_machine_id: str = "",
    healthy_machine_ids: set[str] | None = None,
) -> str | None:
    """Return the governance reason that makes a queued task intentionally non-claimable."""
    metadata = metadata or {}
    queue_state = str(metadata.get("queue_state") or "").strip().lower()
    if queue_state in APPROVAL_HOLD_STATES:
        return str(metadata.get("hold_reason") or queue_state)
    requires_approval = str(metadata.get("requires_approval") or "false").strip().lower() in {"1", "true", "yes"}
    approval_status = str(metadata.get("approval_status") or "").strip().lower()
    if requires_approval and approval_status not in {"approved", "deployed"}:
        return str(metadata.get("hold_reason") or f"approval_{approval_status or 'not_granted'}")
    observed_at = now or datetime.now(UTC)
    if retry_at is not None and retry_at > observed_at:
        return f"retry_backoff_until_{retry_at.isoformat()}"
    healthy = healthy_machine_ids or set()
    if source_machine_id and source_machine_id not in healthy and not task_is_automatic_eligible(metadata):
        return str(metadata.get("hold_reason") or f"required_machine_unavailable:{source_machine_id}")
    return None


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


def select_fallback_target(
    loads: dict[str, dict[str, int]],
    source_machine_id: str,
    *,
    source_unhealthy: bool,
) -> str | None:
    ranked = rank_fallback_targets(loads, source_machine_id)
    if source_unhealthy:
        return ranked[0] if ranked else None
    return next(
        (
            machine_id
            for machine_id in ranked
            if loads[machine_id]["running"] + loads[machine_id]["queued"] < loads[machine_id]["capacity"]
        ),
        None,
    )


def should_reroute_task(
    *,
    source_unhealthy: bool,
    source_running: int,
    assignment_generation: int,
    target_has_room: bool,
    balances_backlog: bool,
    seconds_since_assignment: float,
) -> bool:
    """Move portable work when its source is down, imbalanced, or has failed to claim it."""
    starved = (
        source_running == 0
        and assignment_generation < 2
        and seconds_since_assignment >= QUEUE_STARVATION_SECONDS
    )
    return source_unhealthy or (target_has_room and (balances_backlog or starved))


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
                select id, created_at, next_attempt_at, execution_machine_id, metadata
                from tasks
                where status = 'queued'
                """
            )
            queued_rows = [dict(row) for row in cur.fetchall()]
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
    healthy_ids = {str(row["id"]) for row in machine_load}
    eligible_by_machine = {machine_id: 0 for machine_id in healthy_ids}
    approval_held = 0
    retry_waiting = 0
    machine_bound_unavailable = 0
    reroutable_backlog = 0
    eligible_ages: list[float] = []
    hold_reasons: dict[str, int] = {}
    for row in queued_rows:
        metadata = dict(row.get("metadata") or {})
        retry_at = row.get("next_attempt_at")
        if retry_at is not None and retry_at > observed_at:
            retry_waiting += 1
            reason = queued_hold_reason(metadata, retry_at=retry_at, now=observed_at)
            hold_reasons[reason or "retry_backoff"] = hold_reasons.get(reason or "retry_backoff", 0) + 1
            continue
        if not task_is_claim_eligible(metadata):
            approval_held += 1
            reason = queued_hold_reason(metadata, now=observed_at)
            hold_reasons[reason or "approval_hold"] = hold_reasons.get(reason or "approval_hold", 0) + 1
            continue
        source = str(row.get("execution_machine_id") or "")
        if source in healthy_ids:
            eligible_by_machine[source] += 1
            if task_is_automatic_eligible(metadata) and len(healthy_ids) > 1:
                reroutable_backlog += 1
        elif task_is_automatic_eligible(metadata) and healthy_ids:
            reroutable_backlog += 1
        else:
            machine_bound_unavailable += 1
            reason = queued_hold_reason(
                metadata,
                now=observed_at,
                source_machine_id=source,
                healthy_machine_ids=healthy_ids,
            )
            hold_reasons[reason or f"required_machine_unavailable:{source or 'unassigned'}"] = (
                hold_reasons.get(reason or f"required_machine_unavailable:{source or 'unassigned'}", 0) + 1
            )
            continue
        created_at = row.get("created_at")
        if created_at is not None:
            eligible_ages.append(max(0.0, (observed_at - created_at).total_seconds()))
    queued_eligible = sum(eligible_by_machine.values()) + sum(
        1
        for row in queued_rows
        if (row.get("next_attempt_at") is None or row["next_attempt_at"] <= observed_at)
        and task_is_claim_eligible(dict(row.get("metadata") or {}))
        and str(row.get("execution_machine_id") or "") not in healthy_ids
        and task_is_automatic_eligible(dict(row.get("metadata") or {}))
        and bool(healthy_ids)
    )
    idle_healthy = [
        str(row["id"])
        for row in machine_load
        if int(row.get("running") or 0) == 0 and eligible_by_machine.get(str(row["id"]), 0) == 0
    ]
    drain_eta_minutes = round(queued_eligible / rate_per_minute, 1) if queued_eligible and rate_per_minute > 0 else (0.0 if queued_eligible == 0 else None)
    return {
        "generated_at": observed_at.isoformat(),
        "queued": queued,
        "queued_total": queued,
        "queued_eligible": queued_eligible,
        "approval_held": approval_held,
        "machine_bound_unavailable": machine_bound_unavailable,
        "reroutable_backlog": reroutable_backlog,
        "running": running,
        "stalled_running": stalled,
        "retry_waiting": retry_waiting,
        "hold_reasons": hold_reasons,
        "unexplained_waiting": max(0, queued - queued_eligible - approval_held - retry_waiting - machine_bound_unavailable),
        "oldest_queue_age_seconds": max(eligible_ages, default=0.0),
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
                "no_healthy_machine_idle_while_backlogged": reroutable_backlog == 0 or not idle_healthy,
                "no_unexplained_waiting": queued == queued_eligible + approval_held + retry_waiting + machine_bound_unavailable,
            },
        },
    }


def _reconcile_control_plane(cur: Any, observed_at: datetime, max_moves: int) -> dict[str, Any]:
    """Keep operator and peer-request ledgers aligned with their executable tasks."""
    result = {"operator_requests_synced": 0, "peer_tasks_created": 0, "peer_requests_synced": 0}

    cur.execute(
        """
        select id, routed_task_ids
        from operator_requests
        where status in ('queued', 'running')
        order by priority desc, created_at
        for update skip locked
        limit %s
        """,
        (max_moves * 4,),
    )
    for request in [dict(row) for row in cur.fetchall()]:
        task_ids = [int(value) for value in (request.get("routed_task_ids") or [])]
        if not task_ids:
            continue
        cur.execute(
            "select id, status, result from tasks where id = any(%s::bigint[]) order by id",
            (task_ids,),
        )
        tasks = [dict(row) for row in cur.fetchall()]
        status = derive_parent_status([str(task["status"]) for task in tasks])
        summaries = [str(task.get("result") or "").strip() for task in tasks if task.get("result")]
        cur.execute(
            """
            update operator_requests
            set status = %s,
                response_summary = case when %s <> '' then %s else response_summary end,
                updated_at = %s
            where id = %s and status is distinct from %s
            """,
            (status, "\n\n".join(summaries)[:4000], "\n\n".join(summaries)[:4000], observed_at, request["id"], status),
        )
        result["operator_requests_synced"] += cur.rowcount

    cur.execute(
        """
        select *
        from peer_requests
        where status in ('requested', 'in_progress')
        order by priority desc, created_at
        for update skip locked
        limit %s
        """,
        (max_moves * 4,),
    )
    peer_requests = [dict(row) for row in cur.fetchall()]
    for request in peer_requests:
        task_id = request.get("task_id")
        if task_id is None:
            cur.execute(
                """
                select id
                from agents
                where machine_id = %s and status = 'active'
                order by case when category = %s then 0 else 1 end, id
                limit 1
                """,
                (request["to_machine_id"], request["request_type"]),
            )
            agent = cur.fetchone()
            if agent is None:
                cur.execute(
                    """
                    update peer_requests
                    set response_metadata = response_metadata || %s::jsonb, updated_at = %s
                    where id = %s
                    """,
                    (json.dumps({"hold_reason": f"no_active_agent:{request['to_machine_id']}"}), observed_at, request["id"]),
                )
                continue
            cur.execute(
                """
                insert into tasks (
                    title, agent_id, category, description, priority, metadata, execution_machine_id
                )
                values (%s, %s, 'peer-request', %s, %s, %s::jsonb, %s)
                returning id
                """,
                (
                    f"Peer request #{request['id']}: {request['subject']}",
                    agent["id"],
                    request["body"],
                    request["priority"],
                    json.dumps({
                        "peer_request_id": request["id"],
                        "requested_by": request["from_machine_id"],
                        "project_id": request.get("project_id"),
                    }),
                    request["to_machine_id"],
                ),
            )
            task_id = int(cur.fetchone()["id"])
            cur.execute(
                "update peer_requests set task_id = %s, updated_at = %s where id = %s",
                (task_id, observed_at, request["id"]),
            )
            cur.execute(
                "insert into task_events (task_id, event_type, message) values (%s, 'peer_request_materialized', %s)",
                (task_id, f"Brain steward materialized peer request {request['id']} as executable work."),
            )
            result["peer_tasks_created"] += 1

        cur.execute("select status, result from tasks where id = %s", (task_id,))
        task = cur.fetchone()
        if task is None:
            continue
        task_status = str(task["status"])
        peer_status = (
            "fulfilled" if task_status == "completed"
            else "rejected" if task_status in {"failed", "cancelled"}
            else "in_progress" if task_status == "running"
            else "requested"
        )
        cur.execute(
            """
            update peer_requests
            set status = %s,
                response_body = case when %s is not null then %s else response_body end,
                responder_machine_id = case when %s in ('fulfilled', 'rejected') then to_machine_id else responder_machine_id end,
                responded_at = case when %s in ('fulfilled', 'rejected') then coalesce(responded_at, %s) else responded_at end,
                updated_at = %s
            where id = %s and status is distinct from %s
            """,
            (peer_status, task.get("result"), task.get("result"), peer_status, peer_status, observed_at, observed_at, request["id"], peer_status),
        )
        result["peer_requests_synced"] += cur.rowcount
    return result


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
        "control_plane": {},
    }

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_try_advisory_xact_lock(%s) as acquired", (STEWARD_LOCK_ID,))
            if not bool(cur.fetchone()["acquired"]):
                return {**result, "status": "skipped_locked"}

            result["control_plane"] = _reconcile_control_plane(cur, observed_at, max_moves)

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
                    select t.id, t.title, t.agent_id, t.category, t.metadata, t.updated_at,
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
                    source_load = loads.get(source, {"running": 0, "queued": 0})
                    source_total = source_load["running"] + source_load["queued"]
                    source_unhealthy = source not in healthy
                    target = select_fallback_target(loads, source, source_unhealthy=source_unhealthy)
                    if target is None:
                        continue
                    target_load = loads[target]["running"] + loads[target]["queued"]
                    target_has_room = target_load < loads[target]["capacity"]
                    balances_backlog = source_total > target_load + 1
                    seconds_since_assignment = max(
                        0.0,
                        (observed_at - task["updated_at"]).total_seconds(),
                    )
                    if not should_reroute_task(
                        source_unhealthy=source_unhealthy,
                        source_running=source_load["running"],
                        assignment_generation=int(task.get("assignment_generation") or 0),
                        target_has_room=target_has_room,
                        balances_backlog=balances_backlog,
                        seconds_since_assignment=seconds_since_assignment,
                    ):
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
                        "reason": (
                            "source_unhealthy"
                            if source_unhealthy
                            else "capacity_balance"
                            if balances_backlog
                            else "claim_starvation"
                        ),
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
