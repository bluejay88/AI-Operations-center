from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://100.70.49.32:8088"


def _get_json(url: str, timeout: int = 10) -> tuple[bool, Any, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200, json.loads(response.read().decode()), str(response.status)
    except Exception as exc:  # pragma: no cover - audit output path
        return False, None, repr(exc)


def _post_json(url: str, payload: dict[str, Any], timeout: int = 10) -> tuple[bool, Any, str]:
    data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200, json.loads(response.read().decode()), str(response.status)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode()
        except Exception:
            body = ""
        return False, None, f"{exc.code} {body}"
    except Exception as exc:  # pragma: no cover - audit output path
        return False, None, repr(exc)


def run_audit(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    files = [
        "dashboard/index.html",
        "dashboard/app.js",
        "dashboard/styles.css",
        "ai_ops_center/api.py",
        "ai_ops_center/tasks.py",
        "ai_ops_center/settings.py",
        "config/agents.yaml",
        "config/ai_factory.yaml",
        "prompts/AGENT_PROMPTS.md",
        "docker/publish-laptop-telemetry.ps1",
        "docker/show-heavy-work-overlay.ps1",
        "docker/start-laptop-operations.ps1",
    ]
    for rel in files:
        add(f"file exists: {rel}", (ROOT / rel).exists())

    app_js = (ROOT / "dashboard/app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "dashboard/index.html").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard/styles.css").read_text(encoding="utf-8")
    api_py = (ROOT / "ai_ops_center/api.py").read_text(encoding="utf-8")
    tasks_py = (ROOT / "ai_ops_center/tasks.py").read_text(encoding="utf-8")
    agents_yaml = (ROOT / "config/agents.yaml").read_text(encoding="utf-8")
    factory_yaml = (ROOT / "config/ai_factory.yaml").read_text(encoding="utf-8")

    add("dashboard password screen present", "dashboard-login-form" in index_html)
    add("dashboard API base detection present", "DEFAULT_BRAIN_API" in app_js and "aiOpsApiBase" in app_js)
    add("dashboard safe API loader present", "safeApi" in app_js)
    add("dashboard safe renderer present", "safeRender" in app_js)
    add("dashboard factory payload normalizer present", "normalizeFactory" in app_js)
    add("dashboard task payload normalizer present", "normalizeTasks" in app_js)
    add("dashboard live connection banner present", "api-connection-status" in index_html)
    add("dashboard asset cache bust present", "pet-motion-workers-20260713e" in index_html)
    add("laptop pet keyboard present", "pet-keyboard" in app_js and "pet-keyboard" in styles)
    add("shield siren present", "pet-siren" in app_js and "siren-flash" in styles)
    add("shield no longer spins on scan", "@keyframes pet-scanning { 0% { transform: rotate" not in styles)
    add("pet connecting animation present", "pet-state-connecting" in app_js and "connect-wave" in styles)
    add("pet on-roll animation present", "pet-state-on-roll" in app_js and "roll-burst" in styles)
    add("pet heavy-work animation present", "pet-state-heavy" in app_js and "heavy-glow" in styles)
    add("worker visible duration configured", "work_seconds" in (ROOT / "ai_ops_center/worker.py").read_text(encoding="utf-8"))
    add("laptop heavy overlay script configured", "Hey, don't use me right now" in (ROOT / "docker/show-heavy-work-overlay.ps1").read_text(encoding="utf-8"))
    add("API CORS configured", "CORSMiddleware" in api_py)
    add("API dashboard login configured", "/dashboard/login" in api_py)
    add("API chat task intake configured", "/tasks/intake" in api_py)
    add("API external model workflow configured", "/integrations/workflow" in api_py)
    add("API governed model query configured", "/models/query" in api_py)
    add("API laptop package dispatch configured", "/laptop-packages/dispatch" in api_py)
    add("model solution packet schema configured", "model_solution_packets" in (ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
    add("API security guardian configured", "/security/guardian" in api_py)
    add("task intake splitter configured", "create_chat_task_intake" in tasks_py)
    add("task intake rubric configured", "INTAKE_RUBRIC" in tasks_py)
    add("security monitor agent configured", "security-monitor" in agents_yaml)
    add("rubric auditor agent configured", "rubric-auditor" in agents_yaml)
    add("market intelligence agent configured", "market-intelligence" in agents_yaml)
    add("deployment prechecker agent configured", "deployment-prechecker" in agents_yaml)
    add("agent roster at least 30", agents_yaml.count("- id: ") >= 30, agents_yaml.count("- id: "))
    add("factory has precheck rubrics", "precheck_rubric" in factory_yaml)
    add("factory has Brain evaluation gates", "handoff_gates" in factory_yaml)

    live_checks = [
        ("health endpoint", "/health"),
        ("registry endpoint", "/registry"),
        ("readiness endpoint", "/readiness.json"),
        ("tasks endpoint", "/tasks"),
        ("connections endpoint", "/connections"),
        ("factory endpoint", "/factory"),
        ("NOC endpoint", "/ops2/noc"),
        ("approvals endpoint", "/approvals"),
        ("listener endpoint", "/listener/events"),
        ("operator requests endpoint", "/operator-requests"),
        ("integrations endpoint", "/integrations/status"),
        ("model solutions endpoint", "/models/solutions"),
        ("security guardian endpoint", "/security/guardian"),
        ("Phoenix endpoint", "/phoenix/briefing"),
        ("hourly report endpoint", "/reports/hourly"),
    ]
    live_payloads: dict[str, Any] = {}
    for name, path in live_checks:
        ok, payload, detail = _get_json(f"{base_url}{path}")
        live_payloads[path] = payload
        add(name, ok, detail)

    ok, login_payload, login_detail = _post_json(f"{base_url}/dashboard/login", {"password": "BleujayBrain2026!"})
    add("dashboard login accepts configured password", ok and login_payload and login_payload.get("ok") is True, login_payload or login_detail)

    html_ok = False
    html_detail = ""
    try:
        html = urllib.request.urlopen(f"{base_url}/dashboard/", timeout=10).read().decode()
        html_ok = "dashboard-login-form" in html and "pet-motion-workers-20260713e" in html
        html_detail = "served"
    except Exception as exc:
        html_detail = repr(exc)
    add("live dashboard HTML served with auth assets", html_ok, html_detail)

    noc = live_payloads.get("/ops2/noc") or {}
    workforce = noc.get("ai_workforce") or {}
    add("NOC reports active agents", (workforce.get("active_agents") or 0) >= 18, workforce.get("active_agents"))
    add("NOC reports queued work", (workforce.get("queue_length") or 0) >= 1, workforce.get("queue_length"))
    add("NOC reports completed work", (workforce.get("completed_jobs") or 0) >= 1, workforce.get("completed_jobs"))
    add("NOC has infrastructure telemetry section", "infrastructure" in noc)
    add("NOC has SSH status section", bool(noc.get("ssh_status") is not None))
    add("NOC has security section", "security" in noc)
    add("NOC has collaboration updates", "collaboration" in noc)

    registry = live_payloads.get("/registry") or {}
    add("registry has Brain PC", any(m.get("id") == "brain-gaming-pc" for m in registry.get("machines", [])))
    add("registry has Dev Laptop", any(m.get("id") == "dev-laptop" for m in registry.get("machines", [])))
    add("registry has Research Laptop", any(m.get("id") == "research-laptop" for m in registry.get("machines", [])))
    add("registry has Business Laptop placeholder", any(m.get("id") == "business-laptop" for m in registry.get("machines", [])))
    add("registry has expanded agent roster live", len(registry.get("agents", [])) >= 18, len(registry.get("agents", [])))

    readiness = live_payloads.get("/readiness.json") or {}
    ready_machines = readiness.get("machines", [])
    add("readiness includes laptop states", len(ready_machines) >= 3, len(ready_machines))
    add("Brain is online in readiness", any(m.get("id") == "brain-gaming-pc" and m.get("state") == "online" for m in ready_machines))

    ssh_status = noc.get("ssh_status") or []
    ready_ssh = [s for s in ssh_status if s.get("ssh_noninteractive") is True or s.get("state") == "noninteractive_ready"]
    add("at least one laptop SSH noninteractive-ready", len(ready_ssh) >= 1, ready_ssh)
    add("remote operations require approval path exists", "remote_operation_requests" in (ROOT / "sql/schema.sql").read_text(encoding="utf-8"))

    intake_ok, intake_payload, intake_detail = _post_json(
        f"{base_url}/tasks/intake",
        {
            "title": "Audit intake test: market and dashboard task routing",
            "body": "Route a rich market research and dashboard improvement request to the laptop teams with rubrics.",
            "requester": "audit50",
            "priority": 61,
        },
    )
    add("chat task intake creates routed tasks", intake_ok and bool((intake_payload or {}).get("created_task_ids")), intake_payload or intake_detail)

    passed = sum(1 for check in checks if check["ok"])
    return {"passed": passed, "total": len(checks), "checks": checks}


def main() -> None:
    print(json.dumps(run_audit(), indent=2, default=str))


if __name__ == "__main__":
    main()
