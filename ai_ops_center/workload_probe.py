from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


DEFAULT_BASE_URL = "http://100.70.49.32:8088"


@dataclass(frozen=True)
class WorkloadLane:
    machine_id: str
    agent_id: str
    category: str
    title: str


LANES = [
    WorkloadLane("brain-gaming-pc", "chief-of-staff", "operations", "Brain workload probe: orchestrator lane"),
    WorkloadLane("dev-laptop", "programmer", "development", "Dev workload probe: code lane"),
    WorkloadLane("research-laptop", "research-lead", "research", "Research workload probe: research lane"),
    WorkloadLane("business-laptop", "business-manager", "business", "Business workload probe: business lane"),
]


def _json_request(url: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 10) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {body}") from exc


def _task_by_id(base_url: str, task_id: int) -> dict[str, Any] | None:
    payload = _json_request(f"{base_url}/tasks/{task_id}")
    return payload.get("task")


def _machine_counts(base_url: str, machine_id: str) -> dict[str, int]:
    payload = _json_request(f"{base_url}/readiness.json")
    for machine in payload.get("machines", []):
        if machine.get("id") == machine_id:
            return machine.get("task_counts") or {}
    return {}


def run_probe(
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = 120,
    poll_seconds: float = 2.0,
    machines: list[str] | None = None,
) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    started_at = datetime.now(UTC).isoformat()
    lane_results: list[dict[str, Any]] = []
    machine_filter = set(machines or [])

    for lane in LANES:
        if machine_filter and lane.machine_id not in machine_filter:
            continue
        title = f"{lane.title} [{started_at}]"
        payload = {
            "title": title,
            "agent_id": lane.agent_id,
            "category": lane.category,
            "priority": 100,
            "description": (
                f"Workload probe for {lane.machine_id}. Claim this task, hold it briefly, complete it, "
                "and report the result so the Brain can verify this lane is moving work."
            ),
        }
        created = _json_request(f"{base_url}/tasks", method="POST", payload=payload)
        task_id = int(created["task_id"])
        result = {
            "machine_id": lane.machine_id,
            "agent_id": lane.agent_id,
            "task_id": task_id,
            "queued_seen": False,
            "running_seen": False,
            "completed_seen": False,
            "last_status": "created",
            "counts": {},
            "seconds_to_running": None,
            "seconds_to_completed": None,
        }

        created_at = time.monotonic()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            task = _task_by_id(base_url, task_id)
            counts = _machine_counts(base_url, lane.machine_id)
            result["counts"] = counts
            if task:
                status = task.get("status", "unknown")
                result["last_status"] = status
                result["queued_seen"] = result["queued_seen"] or status == "queued"
                if status == "running" or counts.get("running", 0) > 0:
                    if not result["running_seen"]:
                        result["seconds_to_running"] = round(time.monotonic() - created_at, 2)
                    result["running_seen"] = True
                if status == "completed":
                    result["completed_seen"] = True
                    result["seconds_to_completed"] = round(time.monotonic() - created_at, 2)
                if result["completed_seen"]:
                    break
            time.sleep(poll_seconds)

        result["ok"] = bool(result["completed_seen"])
        lane_results.append(result)

    return {
        "started_at": started_at,
        "base_url": base_url,
        "passed": sum(1 for result in lane_results if result["ok"]),
        "total": len(lane_results),
        "lanes": lane_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and audit one workload probe per AI Operations machine lane.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--machine", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            run_probe(
                base_url=args.base_url,
                timeout_seconds=args.timeout_seconds,
                poll_seconds=args.poll_seconds,
                machines=args.machine,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
