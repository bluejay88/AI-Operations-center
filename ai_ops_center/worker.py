from __future__ import annotations

import time

from .orchestrator import claim_next_task, complete_task, record_heartbeat


def run_worker(machine_id: str, once: bool = False, sleep_seconds: int = 15, work_seconds: int = 4, local: bool = False) -> None:
    while True:
        record_heartbeat(machine_id, local=local)
        task = claim_next_task(machine_id, local=local)
        if task:
            if work_seconds > 0:
                time.sleep(work_seconds)
            result = _simulate_agent_work(task)
            complete_task(task["id"], result, local=local)
        if once:
            return
        time.sleep(sleep_seconds)


def _simulate_agent_work(task: dict) -> str:
    return (
        f"Agent {task['agent_id']} completed planning pass for '{task['title']}'. "
        "Next production version should connect this task type to its approved external tool, "
        "store artifacts, and request human approval for sensitive actions."
    )
