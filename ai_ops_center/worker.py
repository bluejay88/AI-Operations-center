from __future__ import annotations

import logging
import time

from .brain_bus import acknowledge_speaker_message, speaker_feed, submit_listener_event
from .migrations import apply_migrations
from .orchestrator import claim_next_task, complete_task, fail_task, record_heartbeat
from .queue_manager import steward_queue

logger = logging.getLogger(__name__)


def run_worker(machine_id: str, once: bool = False, sleep_seconds: int = 15, work_seconds: int = 4, local: bool = False) -> None:
    apply_migrations(local=local)
    last_steward_at = 0.0
    while True:
        record_heartbeat(machine_id, local=local)
        _consume_machine_messages(machine_id, local=local)
        if time.monotonic() - last_steward_at >= 5:
            try:
                steward_queue(local=local)
            except Exception:
                logger.exception("Queue steward failed; worker will continue claiming eligible tasks")
            last_steward_at = time.monotonic()
        task = claim_next_task(machine_id, local=local)
        if task:
            record_heartbeat(machine_id, active_task_id=task["id"], local=local)
            try:
                if work_seconds > 0:
                    time.sleep(work_seconds)
                result = _simulate_agent_work(task)
                completed = complete_task(task["id"], result, task["claim_token"], machine_id, local=local)
                if completed:
                    _report_task_completion(machine_id, task, result, local=local)
            except Exception as exc:
                fail_task(task["id"], str(exc), task["claim_token"], machine_id, local=local)
                if once:
                    raise
        if once:
            return
        if task:
            continue
        time.sleep(sleep_seconds)


def _consume_machine_messages(machine_id: str, local: bool = False) -> int:
    """Acknowledge direct machine messages and emit auditable proof of receipt."""
    try:
        messages = speaker_feed(machine_id, local=local).get("messages", [])
    except Exception:
        logger.exception("Unable to read speaker feed for %s", machine_id)
        return 0

    acknowledged = 0
    for message in messages:
        if message.get("target_id") != machine_id or message.get("status") == "acknowledged":
            continue
        try:
            submit_listener_event(
                source_type="machine",
                source_id=machine_id,
                event_type="speaker_message_received",
                subject=f"Received: {message['subject']}",
                body=f"{machine_id} received speaker message {message['id']} and is listening.",
                priority=int(message.get("priority") or 50),
                metadata={"speaker_message_id": message["id"], "machine_id": machine_id},
                local=local,
            )
            acknowledge_speaker_message(message["id"], actor=machine_id, local=local)
            acknowledged += 1
        except Exception:
            logger.exception("Unable to acknowledge speaker message %s", message.get("id"))
    return acknowledged


def _report_task_completion(machine_id: str, task: dict, result: str, local: bool = False) -> None:
    try:
        submit_listener_event(
            source_type="machine",
            source_id=machine_id,
            event_type="task_completed",
            subject=f"Task completed: {task['title']}",
            body=result,
            priority=int(task.get("priority") or 50),
            metadata={
                "task_id": task["id"],
                "agent_id": task["agent_id"],
                "machine_id": machine_id,
                "claim_token": task["claim_token"],
            },
            local=local,
        )
    except Exception:
        logger.exception("Task %s completed but its listener pulse failed", task.get("id"))


def _simulate_agent_work(task: dict) -> str:
    return (
        f"Agent {task['agent_id']} completed planning pass for '{task['title']}'. "
        "Next production version should connect this task type to its approved external tool, "
        "store artifacts, and request human approval for sensitive actions."
    )
