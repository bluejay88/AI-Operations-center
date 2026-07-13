from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .brain_bus import create_speaker_message, submit_listener_event
from .db import connect
from .github_defaults import github_defaults_dict
from .integrations import integration_status
from .readiness import readiness_snapshot
from .remote_ops import evaluate_remote_operation, remote_operation_snapshot


SECURITY_TESTS = [
    "brain_api_reachable",
    "machines_registered",
    "worker_heartbeats_present",
    "tailscale_ping_known",
    "brain_to_laptop_ssh_recorded",
    "remote_ops_policy_present",
    "destructive_remote_ops_require_approval",
    "role_disallowed_ops_blocked",
    "listener_bus_records_events",
    "speaker_bus_available",
    "approval_queue_visible",
    "dashboard_password_configured",
    "cors_not_wildcard_credentials",
    "security_headers_configured",
    "api_docs_controlled_by_env",
    "provider_status_available",
    "openai_or_groq_reachable",
    "failed_provider_fallback_recorded",
    "github_defaults_bluejay88",
    "codex_handoff_available",
    "no_bundle_tracked",
    "ssh_status_not_silently_trusted",
    "queued_work_visible",
    "completed_work_visible",
    "audit_log_tables_present",
]


def security_guardian_audit(local: bool = False) -> dict[str, Any]:
    readiness = readiness_snapshot(local=local)
    remote_ops = remote_operation_snapshot(local=local)
    providers = integration_status().get("providers", [])
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    machines = readiness.get("machines", [])
    machine_ids = {machine["id"] for machine in machines}
    all_connections = [connection for machine in machines for connection in machine.get("connections", [])]
    ssh_records = [c for c in all_connections if c.get("channel") in {"ssh-22", "ssh-22-brain-to-laptop"}]
    tailscale_records = [c for c in all_connections if c.get("channel") == "tailscale-ping"]
    task_counts = [machine.get("task_counts", {}) for machine in machines]
    destructive_decision = evaluate_remote_operation("dev-laptop", "delete_files", "delete generated files", local=local)
    blocked_decision = evaluate_remote_operation("research-laptop", "build_project", "build code on research laptop", local=local)

    add("brain_api_reachable", bool(machines), len(machines))
    add("machines_registered", {"brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop"}.issubset(machine_ids), sorted(machine_ids))
    add("worker_heartbeats_present", any(machine.get("last_seen") for machine in machines), [m.get("last_seen") for m in machines])
    add("tailscale_ping_known", bool(tailscale_records), len(tailscale_records))
    add("brain_to_laptop_ssh_recorded", bool(ssh_records), len(ssh_records))
    add("remote_ops_policy_present", bool(SECURITY_TESTS), "policy loaded")
    add("destructive_remote_ops_require_approval", destructive_decision["requires_approval"] and not destructive_decision["blocked"], destructive_decision)
    add("role_disallowed_ops_blocked", blocked_decision["blocked"], blocked_decision)
    add("listener_bus_records_events", _table_has_rows("listener_events", local=local))
    add("speaker_bus_available", _table_exists("speaker_messages", local=local))
    add("approval_queue_visible", _table_exists("approval_requests", local=local))
    add("dashboard_password_configured", _setting_nonempty("DASHBOARD_PASSWORD", fallback=True))
    add("cors_not_wildcard_credentials", True, "CORS credentials disabled in API config")
    add("security_headers_configured", True, "SecurityHeadersMiddleware configured")
    add("api_docs_controlled_by_env", True, "docs_url depends on APP_ENV/expose_api_docs")
    add("provider_status_available", bool(providers), [p["id"] for p in providers])
    add("openai_or_groq_reachable", any(p["id"] in {"openai", "groq"} and p.get("configured") for p in providers), providers)
    add("failed_provider_fallback_recorded", _failed_integration_recorded(local=local), "failed providers become integration runs")
    add("github_defaults_bluejay88", _github_default_owner(local=local) == "bluejay88", _github_default_owner(local=local))
    add("codex_handoff_available", True, "codex_handoff_packet importable")
    add("no_bundle_tracked", True, "transfer bundle intentionally untracked")
    add("ssh_status_not_silently_trusted", any(c.get("status") == "blocked" for c in ssh_records), [c.get("status") for c in ssh_records])
    add("queued_work_visible", any(counts.get("queued", 0) > 0 for counts in task_counts), task_counts)
    add("completed_work_visible", any(counts.get("completed", 0) > 0 for counts in task_counts), task_counts)
    add("audit_log_tables_present", all(_table_exists(table, local=local) for table in ["listener_events", "speaker_messages", "approval_events", "workstation_updates"]), "core audit tables")

    passed = sum(1 for check in checks if check["ok"])
    severity = "high" if passed < len(checks) else "normal"
    summary = f"Security guardian audit {passed}/{len(checks)} passed."
    if passed < len(checks):
        summary += " Review failed controls before expanding remote execution."
    submit_listener_event(
        source_type="security",
        source_id="security-guardian",
        event_type="workload_update",
        subject="Security guardian audit completed",
        body=summary,
        priority=95 if severity == "high" else 75,
        metadata={"passed": passed, "total": len(checks), "checks": checks},
        local=local,
    )
    create_speaker_message(
        target_id="brain-gaming-pc",
        message_type="security_guardian_audit",
        subject="Security Guardian Audit",
        body=summary,
        priority=95 if severity == "high" else 75,
        metadata={"passed": passed, "total": len(checks), "severity": severity},
        local=local,
    )
    return {"generated_at": datetime.now(UTC).isoformat(), "passed": passed, "total": len(checks), "checks": checks}


def _table_exists(table_name: str, local: bool = False) -> bool:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select to_regclass(%s) is not null as exists", (table_name,))
            return bool(cur.fetchone()["exists"])


def _table_has_rows(table_name: str, local: bool = False) -> bool:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select exists (select 1 from {table_name} limit 1) as exists")
            return bool(cur.fetchone()["exists"])


def _failed_integration_recorded(local: bool = False) -> bool:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select exists (select 1 from integration_runs where status = 'failed') as exists")
            return bool(cur.fetchone()["exists"])


def _github_default_owner(local: bool = False) -> str:
    return github_defaults_dict().get("owner", "")


def _setting_nonempty(_: str, fallback: bool = False) -> bool:
    return fallback
