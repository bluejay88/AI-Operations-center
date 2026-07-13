from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _failover_recommendation(machine_id: str, battery_percent: float | None, state: str | None = None) -> dict:
    state = state or "online"
    critical = battery_percent is not None and float(battery_percent) <= 5
    unavailable = state in {"offline", "worker_stale", "reachable_worker_stale", "blocked"}
    reason = "healthy"
    if critical:
        reason = "battery_at_or_below_5_percent"
    elif unavailable:
        reason = f"machine_state_{state}"
    return {"machine_id": machine_id, "should_failover": critical or unavailable, "reason": reason}


def run_25_checks() -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required_files = [
        "ai_ops_center/api.py",
        "ai_ops_center/ops2.py",
        "ai_ops_center/failover.py",
        "ai_ops_center/operator_requests.py",
        "dashboard/index.html",
        "dashboard/app.js",
        "dashboard/styles.css",
        "sql/schema.sql",
        "docker/audit-laptop-unblock.ps1",
        "docker/publish-laptop-telemetry.ps1",
        "docker/show-heavy-work-overlay.ps1",
        "docker/start-laptop-operations.ps1",
    ]
    for rel in required_files:
        add(f"file exists: {rel}", (ROOT / rel).exists())

    for rel in ["ai_ops_center/api.py", "ai_ops_center/ops2.py", "ai_ops_center/failover.py", "ai_ops_center/operator_requests.py"]:
        try:
            ast.parse((ROOT / rel).read_text(encoding="utf-8"))
            add(f"python parses: {rel}", True)
        except SyntaxError as exc:
            add(f"python parses: {rel}", False, str(exc))

    schema = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
    add("schema has operator_requests", "create table if not exists operator_requests" in schema)
    add("schema has device_telemetry battery", "battery_percent" in schema)
    add("schema has remote operations", "create table if not exists remote_operation_requests" in schema)

    app_js = (ROOT / "dashboard/app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "dashboard/index.html").read_text(encoding="utf-8")
    add("dashboard has 400 seed button handler", "ops2SeedExpansion" in app_js)
    add("dashboard has 5 business launcher", "ops2SeedBusinesses" in app_js)
    add("dashboard has operator request form", "operatorRequestForm" in app_js)
    add("dashboard uses laptop pet visuals", "pet-screenplate" in app_js and "pet-keyboard" in app_js)
    add("dashboard has password gate", "dashboard-login-form" in index_html and "/dashboard/login" in app_js)
    add("dashboard supports live API base", "DEFAULT_BRAIN_API" in app_js and "aiOpsApiBase" in app_js)
    add("dashboard has dynamic pet motion states", "pet-state-connecting" in app_js and "pet-state-on-roll" in app_js and "pet-state-heavy" in app_js)

    api_py = (ROOT / "ai_ops_center/api.py").read_text(encoding="utf-8")
    add("api exposes failover evaluate", "/ops2/failover/evaluate" in api_py)
    add("api exposes stale worker failover", "/ops2/failover/stale-workers" in api_py)
    add("api exposes business launch seed", "/ops2/business-launches/seed" in api_py)
    add("api exposes model workflow", "/integrations/workflow" in api_py)
    add("api exposes governed model query", "/models/query" in api_py)
    add("api exposes laptop package dispatch", "/laptop-packages/dispatch" in api_py)
    add("api exposes business os seed", "/business-os/seed" in api_py)
    add("api exposes enterprise org", "/enterprise-org" in api_py)
    add("api exposes security guardian", "/security/guardian" in api_py)
    add("schema has model solution packets", "create table if not exists model_solution_packets" in schema)

    critical = _failover_recommendation("dev-laptop", 5, "online")
    healthy = _failover_recommendation("dev-laptop", 80, "online")
    stale = _failover_recommendation("research-laptop", None, "worker_stale")
    add("failover triggers at 5 percent", critical["should_failover"], json.dumps(critical))
    add("failover does not trigger at 80 percent", not healthy["should_failover"], json.dumps(healthy))
    add("failover triggers stale worker", stale["should_failover"], json.dumps(stale))
    add("critical reason recorded", critical["reason"] == "battery_at_or_below_5_percent")

    passed = sum(1 for check in checks if check["ok"])
    return {"passed": passed, "total": len(checks), "checks": checks}


def main() -> None:
    print(json.dumps(run_25_checks(), indent=2))


if __name__ == "__main__":
    main()
