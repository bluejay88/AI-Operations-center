from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .config import load_machines
from .connectivity import connection_snapshot
from .db import connect


ONBOARD_COMMANDS = {
    "business-laptop": (
        "powershell -ExecutionPolicy Bypass -File docker\\onboard-laptop.ps1 "
        "-MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale"
    ),
    "research-laptop": (
        "powershell -ExecutionPolicy Bypass -File docker\\onboard-laptop.ps1 "
        "-MachineId research-laptop -BrainHost 100.70.49.32 -RenameTailscale"
    ),
    "dev-laptop": (
        "powershell -ExecutionPolicy Bypass -File docker\\update-worker-from-git.ps1 "
        "-MachineId dev-laptop -BrainHost 100.70.49.32"
    ),
}


def readiness_snapshot(local: bool = False, stale_after_minutes: int = 1) -> dict:
    cutoff = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
    configured_machines = {machine["id"]: machine for machine in load_machines()}

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    m.id, m.name, m.role, m.responsibilities, m.capacity_weight,
                    coalesce(s.last_seen_at, max(h.created_at)) as last_seen,
                    s.status as current_status,
                    s.hostname
                from machines m
                left join machine_status_current s on s.machine_id = m.id
                left join machine_heartbeats h on h.machine_id = m.id
                group by m.id, m.name, m.role, m.responsibilities, m.capacity_weight,
                    s.last_seen_at, s.status, s.hostname
                order by
                    case m.role
                        when 'brain' then 0
                        when 'development' then 1
                        when 'research' then 2
                        when 'business' then 3
                        else 4
                    end,
                    m.id
                """
            )
            machines = cur.fetchall()

            cur.execute(
                """
                select coalesce(t.execution_machine_id, a.machine_id) as machine_id, t.status, count(*) as count
                from tasks t
                join agents a on a.id = t.agent_id
                group by coalesce(t.execution_machine_id, a.machine_id), t.status
                order by coalesce(t.execution_machine_id, a.machine_id), t.status
                """
            )
            task_rows = cur.fetchall()

            cur.execute(
                """
                select distinct on (machine_id)
                    machine_id, cpu_count, cpu_score, memory_total_mb, disk_write_mb_s,
                    brain_latency_ms, docker_available, created_at
                from machine_benchmarks
                order by machine_id, created_at desc
                """
            )
            benchmarks = {row["machine_id"]: row for row in cur.fetchall()}

            cur.execute(
                """
                select machine_id, count(*) as active_agent_count
                from agents
                where status = 'active'
                group by machine_id
                """
            )
            active_agents = {row["machine_id"]: row["active_agent_count"] for row in cur.fetchall()}

    task_counts: dict[str, dict[str, int]] = {}
    global_task_counts: dict[str, int] = {}
    for row in task_rows:
        count = int(row["count"])
        task_counts.setdefault(row["machine_id"], {})[row["status"]] = count
        global_task_counts[row["status"]] = global_task_counts.get(row["status"], 0) + count

    connections = connection_snapshot(local=local)
    connections_by_target: dict[str, list[dict]] = {}
    for connection in connections:
        connections_by_target.setdefault(connection["target_machine_id"], []).append(connection)

    machines = [dict(machine) for machine in machines]
    for machine in machines:
        last_seen = machine["last_seen"]
        machine_connections = connections_by_target.get(machine["id"], [])
        tailscale_online = any(
            connection["channel"] == "tailscale-ping" and connection["status"] == "online"
            for connection in machine_connections
        )
        if last_seen is None and tailscale_online:
            state = "reachable_not_onboarded"
        elif last_seen is None:
            state = "never_seen"
        elif last_seen < cutoff and tailscale_online:
            state = "reachable_worker_stale"
        elif last_seen < cutoff:
            state = "worker_stale"
        else:
            state = machine["current_status"] or "online"
        machine["state"] = state
        machine["task_counts"] = task_counts.get(machine["id"], {})
        machine["lifetime_task_counts"] = dict(machine["task_counts"])
        machine["completed_tasks_total"] = int(machine["task_counts"].get("completed", 0))
        machine["active_agent_count"] = active_agents.get(machine["id"], 0)
        machine["workforce_status"] = configured_machines.get(machine["id"], {}).get("workforce_status", "unassigned")
        machine["employment_status"] = machine["workforce_status"]
        machine["latest_benchmark"] = dict(benchmarks[machine["id"]]) if machine["id"] in benchmarks else None
        machine["connections"] = machine_connections
        machine["next_command"] = ONBOARD_COMMANDS.get(machine["id"]) if state != "online" else None

    laptops = [machine for machine in machines if machine["role"] != "brain"]
    connected_states = {"online", "reachable_not_onboarded", "reachable_worker_stale"}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "stale_after_minutes": stale_after_minutes,
        "summary": {
            "registered_laptops": len(laptops),
            "connected_laptops": sum(machine["state"] in connected_states for machine in laptops),
            "active_laptops": sum(
                machine["state"] == "online" and machine["workforce_status"] == "employed" for machine in laptops
            ),
            "worker_online_laptops": sum(machine["state"] == "online" for machine in laptops),
            "employed_laptops": sum(machine["workforce_status"] == "employed" for machine in laptops),
            "assigned_laptops": sum(
                int(machine["task_counts"].get("queued", 0)) + int(machine["task_counts"].get("running", 0)) > 0
                for machine in laptops
            ),
        },
        "task_summary": {
            "scope": "lifetime",
            "status_counts": global_task_counts,
            "completed_total": int(global_task_counts.get("completed", 0)),
            "by_machine": task_counts,
            "contract": {
                "source": "database_aggregate",
                "recent_list_independent": True,
                "completed_equals_machine_sum": int(global_task_counts.get("completed", 0))
                == sum(int(counts.get("completed", 0)) for counts in task_counts.values()),
            },
        },
        "machines": machines,
        "next_gates": [
            "Dev Agent is ready when it is worker-online, has a benchmark, and can complete a development task.",
            "Research Agent is ready when it checks in and completes a grant or opportunity task.",
            "Business Agent is ready when it checks in and completes a lead generation or business task.",
            "Remote desktop/SSH is required before the brain can show popups or install apps without someone running commands on each laptop.",
        ],
    }


def readiness_report(local: bool = False, stale_after_minutes: int = 1) -> str:
    snapshot = readiness_snapshot(local=local, stale_after_minutes=stale_after_minutes)

    lines = [
        "# AI Operations Readiness",
        f"Generated: {snapshot['generated_at']}",
        "",
        "## Machines",
    ]

    for machine in snapshot["machines"]:
        counts = machine["task_counts"]
        queued = counts.get("queued", 0)
        running = counts.get("running", 0)
        completed = counts.get("completed", 0)
        lines.append(
            f"- {machine['id']} ({machine['role']}): {machine['state']}; "
            f"last_seen={machine['last_seen'] or 'never'}; tasks queued={queued}, running={running}, completed={completed}"
        )

        benchmark = machine["latest_benchmark"]
        if benchmark:
            lines.append(
                f"  Benchmark: cpu_count={benchmark['cpu_count']}, cpu_score={benchmark['cpu_score']}, "
                f"disk_write_mb_s={benchmark['disk_write_mb_s']}, "
                f"latency_ms={benchmark['brain_latency_ms']}, docker={benchmark['docker_available']}"
            )
        elif machine["id"] != "brain-gaming-pc":
            lines.append("  Benchmark: not recorded yet")

        if machine["next_command"]:
            lines.append(f"  Next command: {machine['next_command']}")

    lines.extend(["", "## Next Gate"])
    lines.extend(f"- {gate}" for gate in snapshot["next_gates"])
    return "\n".join(lines)
