from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .db import connect


ROOT = Path(__file__).resolve().parent.parent
FACTORY_PATH = ROOT / "config" / "ai_factory.yaml"


FALLBACK_AGENT_MAP = {
    "business-manager": "project-coordinator",
    "finance-manager": "project-coordinator",
    "social-media": "content-engine",
    "lead-generation": "research-lead",
    "marketing-agent": "content-engine",
}


def factory_snapshot(local: bool = False) -> dict[str, Any]:
    model = yaml.safe_load(FACTORY_PATH.read_text(encoding="utf-8"))
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select a.machine_id, t.status, count(*) as count
                from tasks t
                join agents a on a.id = t.agent_id
                group by a.machine_id, t.status
                """
            )
            task_counts = cur.fetchall()
            cur.execute(
                """
                select t.id, t.title, t.agent_id, a.machine_id, t.category, t.priority, t.status, t.updated_at
                from tasks t
                join agents a on a.id = t.agent_id
                where t.status in ('queued', 'running')
                order by t.priority desc, t.created_at asc
                limit 30
                """
            )
            active_tasks = [dict(row) for row in cur.fetchall()]

    counts_by_machine: dict[str, dict[str, int]] = {}
    for row in task_counts:
        counts_by_machine.setdefault(row["machine_id"], {})[row["status"]] = row["count"]

    for machine in model["machines"]:
        machine["live_task_counts"] = counts_by_machine.get(machine["id"], {})

    model["active_tasks"] = active_tasks
    model["business_fallback_map"] = FALLBACK_AGENT_MAP
    return model


def redistribute_business_queue(local: bool = False) -> list[dict[str, Any]]:
    reassigned: list[dict[str, Any]] = []
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for source_agent, fallback_agent in FALLBACK_AGENT_MAP.items():
                cur.execute(
                    """
                    update tasks
                    set agent_id = %s,
                        metadata = metadata || jsonb_build_object(
                            'redistributed_from_agent', %s::text,
                            'redistributed_reason', 'business-laptop unavailable',
                            'redistributed_to_agent', %s::text
                        ),
                        updated_at = now()
                    where status = 'queued'
                      and agent_id = %s
                    returning id, title, agent_id
                    """,
                    (fallback_agent, source_agent, fallback_agent, source_agent),
                )
                rows = cur.fetchall()
                for row in rows:
                    cur.execute(
                        """
                        insert into task_events (task_id, event_type, message)
                        values (%s, 'redistributed', %s)
                        """,
                        (
                            row["id"],
                            f"Business continuity reassigned task from {source_agent} to {fallback_agent}.",
                        ),
                    )
                    reassigned.append(
                        {
                            "task_id": row["id"],
                            "title": row["title"],
                            "from_agent": source_agent,
                            "to_agent": fallback_agent,
                        }
                    )
        conn.commit()
    return reassigned
