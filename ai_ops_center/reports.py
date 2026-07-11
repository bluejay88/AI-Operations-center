from __future__ import annotations

from datetime import UTC, datetime

from .db import connect


def generate_report(report_type: str, local: bool = False) -> str:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as count from agents where status = 'active'")
            active_agents = cur.fetchone()["count"]
            cur.execute("select status, count(*) as count from tasks group by status order by status")
            task_counts = cur.fetchall()
            cur.execute(
                """
                select title, agent_id, category, priority, status
                from tasks
                order by priority desc, created_at desc
                limit 12
                """
            )
            top_tasks = cur.fetchall()
            cur.execute(
                """
                select machine_id, max(created_at) as last_seen
                from machine_heartbeats
                group by machine_id
                order by machine_id
                """
            )
            heartbeats = cur.fetchall()

    lines = [
        f"# {report_type.title()} AI Operations Report",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        f"Active agents: {active_agents}",
        "",
        "## Task Status",
    ]
    if task_counts:
        lines.extend(f"- {row['status']}: {row['count']}" for row in task_counts)
    else:
        lines.append("- No tasks yet.")

    lines.extend(["", "## Highest Priority Work"])
    if top_tasks:
        lines.extend(
            f"- P{row['priority']} [{row['status']}] {row['title']} ({row['agent_id']}, {row['category']})"
            for row in top_tasks
        )
    else:
        lines.append("- No priority tasks queued.")

    lines.extend(["", "## Machine Heartbeats"])
    if heartbeats:
        lines.extend(f"- {row['machine_id']}: {row['last_seen']}" for row in heartbeats)
    else:
        lines.append("- No worker heartbeats recorded.")

    lines.extend(
        [
            "",
            "## Revenue Focus",
            "- Push website builds, AI maintenance subscriptions, content packages, digital products, and research briefs.",
            "- Track leads, conversion rate, recurring revenue, delivery time, and gross margin before scaling the workforce.",
        ]
    )
    return "\n".join(lines)

