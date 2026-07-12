from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .db import connect


def machine_status(local: bool = False, stale_after_minutes: int = 5) -> str:
    stale_after = datetime.now(UTC) - timedelta(minutes=stale_after_minutes)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    m.id,
                    m.name,
                    m.role,
                    max(h.created_at) as last_seen
                from machines m
                left join machine_heartbeats h on h.machine_id = m.id
                group by m.id, m.name, m.role
                order by
                    case m.role
                        when 'brain' then 0
                        when 'business' then 1
                        when 'research' then 2
                        when 'development' then 3
                        else 9
                    end,
                    m.id
                """
            )
            rows = cur.fetchall()

    lines = ["# AI Operations Machine Status", ""]
    if not rows:
        return "\n".join(lines + ["No machines are registered. Run `seed` first."])

    for row in rows:
        last_seen = row["last_seen"]
        if last_seen is None:
            state = "not seen yet"
        elif last_seen < stale_after:
            state = f"stale, last seen {last_seen.isoformat()}"
        else:
            state = f"online, last seen {last_seen.isoformat()}"
        lines.append(f"- {row['id']} ({row['role']}): {state}")
    return "\n".join(lines)

