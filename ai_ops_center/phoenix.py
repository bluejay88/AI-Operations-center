from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .db import connect
from .factory import factory_snapshot
from .readiness import readiness_snapshot
from .reports import generate_report
from .tasks import task_snapshot


ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS_DIR = ROOT / "instructions"
PROMPTS_PATH = ROOT / "prompts" / "AGENT_PROMPTS.md"


def laptop_instruction(machine_id: str) -> str:
    path = INSTRUCTIONS_DIR / f"{machine_id}.md"
    if not path.exists():
        valid = ", ".join(sorted(p.stem for p in INSTRUCTIONS_DIR.glob("*.md")))
        raise ValueError(f"No instruction file for {machine_id}. Valid files: {valid}")
    return path.read_text(encoding="utf-8")


def prompt_pack() -> str:
    return PROMPTS_PATH.read_text(encoding="utf-8")


def phoenix_snapshot(local: bool = False) -> dict[str, Any]:
    readiness = readiness_snapshot(local=local)
    factory = factory_snapshot(local=local)
    tasks = task_snapshot(limit=30, local=local)
    queued = [task for task in tasks if task["status"] == "queued"]
    running = [task for task in tasks if task["status"] == "running"]
    completed = [task for task in tasks if task["status"] == "completed"]

    machine_states = {
        machine["id"]: {
            "state": machine["state"],
            "role": machine["role"],
            "task_counts": machine["task_counts"],
            "next_command": machine["next_command"],
        }
        for machine in readiness["machines"]
    }

    recommendations: list[str] = []
    dev = machine_states.get("dev-laptop", {})
    research = machine_states.get("research-laptop", {})
    business = machine_states.get("business-laptop", {})

    if dev.get("state") != "online":
        recommendations.append("Update and restart the Dev Laptop worker so queued build tasks can move.")
    if research.get("state") != "online":
        recommendations.append("Confirm the Research Laptop worker is running because lead and grant work is assigned there.")
    if business.get("state") != "online":
        recommendations.append("Keep redistributing Business Laptop work until Business Laptop is onboarded and heartbeating.")
    if queued:
        recommendations.append(f"Highest queued task: P{queued[0]['priority']} {queued[0]['title']} on {queued[0]['machine_id']}.")
    if not recommendations:
        recommendations.append("All major workers are online; keep pressure on revenue tasks and quality gates.")

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "persona": "Phoenix",
        "mission": "Voice and command interface for the Brain PC AI Operations Center.",
        "readiness": readiness,
        "factory": factory,
        "task_summary": {
            "queued": len(queued),
            "running": len(running),
            "completed": len(completed),
        },
        "machine_states": machine_states,
        "recommendations": recommendations,
    }


def phoenix_briefing(local: bool = False) -> str:
    snapshot = phoenix_snapshot(local=local)
    states = snapshot["machine_states"]
    task_summary = snapshot["task_summary"]
    lines = [
        "Phoenix online.",
        f"Generated {snapshot['generated_at']}.",
        (
            f"Task floor status: {task_summary['queued']} queued, "
            f"{task_summary['running']} running, {task_summary['completed']} completed in the current view."
        ),
        "",
        "Machine status:",
    ]
    for machine_id, machine in states.items():
        counts = machine["task_counts"]
        lines.append(
            f"- {machine_id}: {machine['state']}; queued={counts.get('queued', 0)}, "
            f"running={counts.get('running', 0)}, completed={counts.get('completed', 0)}"
        )
        if machine["next_command"]:
            lines.append(f"  Next command: {machine['next_command']}")

    lines.extend(["", "Recommendations:"])
    lines.extend(f"- {item}" for item in snapshot["recommendations"])
    lines.extend(["", "Operating note:", generate_report("hourly", local=local).split("## Revenue Focus", maxsplit=1)[-1].strip()])
    return "\n".join(lines)


def record_phoenix_event(
    event_type: str,
    subject: str,
    body: str,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into phoenix_events (event_type, subject, body, metadata)
                values (%s, %s, %s, %s::jsonb)
                returning id
                """,
                (event_type, subject, body, json.dumps(metadata or {})),
            )
            event_id = cur.fetchone()["id"]
        conn.commit()
    return int(event_id)

