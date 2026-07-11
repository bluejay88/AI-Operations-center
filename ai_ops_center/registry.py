from __future__ import annotations

import json
from typing import Any

from .config import load_agents, load_machines, load_revenue_strategy
from .db import connect


def seed_registry(local: bool = False) -> None:
    agents = load_agents()
    machines = load_machines()
    revenue_strategy = load_revenue_strategy()

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for machine in machines:
                cur.execute(
                    """
                    insert into machines (id, name, role, responsibilities, capacity_weight, services)
                    values (%s, %s, %s, %s::jsonb, %s, %s::jsonb)
                    on conflict (id) do update set
                        name = excluded.name,
                        role = excluded.role,
                        responsibilities = excluded.responsibilities,
                        capacity_weight = excluded.capacity_weight,
                        services = excluded.services,
                        updated_at = now()
                    """,
                    (
                        machine["id"],
                        machine["name"],
                        machine["role"],
                        json.dumps(machine.get("responsibilities", [])),
                        machine.get("capacity_weight", 1),
                        json.dumps(machine.get("services", [])),
                    ),
                )

            for agent in agents:
                cur.execute(
                    """
                    insert into agents (id, name, machine_id, category, mission, cadence, tools, guardrails, status)
                    values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, 'active')
                    on conflict (id) do update set
                        name = excluded.name,
                        machine_id = excluded.machine_id,
                        category = excluded.category,
                        mission = excluded.mission,
                        cadence = excluded.cadence,
                        tools = excluded.tools,
                        guardrails = excluded.guardrails,
                        status = excluded.status,
                        updated_at = now()
                    """,
                    (
                        agent["id"],
                        agent["name"],
                        agent["machine"],
                        agent["category"],
                        agent["mission"],
                        agent["cadence"],
                        json.dumps(agent.get("tools", [])),
                        json.dumps(agent.get("guardrails", [])),
                    ),
                )

            cur.execute(
                """
                insert into system_state (key, value)
                values ('revenue_strategy', %s::jsonb)
                on conflict (key) do update set value = excluded.value, updated_at = now()
                """,
                (json.dumps(revenue_strategy),),
            )
        conn.commit()


def registry_snapshot(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from machines order by id")
            machines = cur.fetchall()
            cur.execute("select * from agents order by category, id")
            agents = cur.fetchall()
    return {"machines": machines, "agents": agents}

