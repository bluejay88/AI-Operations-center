from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .db import connect


def record_connection(
    source_machine_id: str,
    target_machine_id: str,
    channel: str,
    status: str,
    latency_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into machine_connections (
                    source_machine_id, target_machine_id, channel, status,
                    latency_ms, last_checked_at, metadata, updated_at
                )
                values (%s, %s, %s, %s, %s, now(), %s::jsonb, now())
                on conflict (source_machine_id, target_machine_id, channel) do update set
                    status = excluded.status,
                    latency_ms = excluded.latency_ms,
                    last_checked_at = excluded.last_checked_at,
                    metadata = excluded.metadata,
                    updated_at = now()
                """,
                (
                    source_machine_id,
                    target_machine_id,
                    channel,
                    status,
                    latency_ms,
                    _json_metadata(metadata),
                ),
            )
        conn.commit()


DEFAULT_STALE_AFTER_SECONDS = 90
ONLINE_STATUSES = {"online", "connected", "healthy", "ok", "reachable", "ready"}
FAILURE_STATUSES = {"auth_failed", "blocked", "error", "failed", "offline", "refused", "timeout", "unreachable"}

# Stable machine-readable codes used by dashboards, agents, and remediation
# workflows.  Remediations are advisory: privileged or trust-changing actions
# remain subject to Brain review rather than being silently executed.
REMEDIATION_CATALOG: dict[str, dict[str, Any]] = {
    "refresh-node-report": {
        "title": "Refresh node connectivity report",
        "actions": ["Run a fresh connectivity probe from the Brain and node.", "Republish node telemetry."],
        "automatic_safe": True,
        "requires_brain_review": False,
    },
    "restore-tailscale-path": {
        "title": "Restore the private mesh path",
        "actions": ["Verify Tailscale is running and the node is signed in.", "Check the node name and private-mesh reachability."],
        "automatic_safe": False,
        "requires_brain_review": True,
    },
    "open-ssh-service-path": {
        "title": "Restore the SSH service path",
        "actions": ["Verify the SSH service is running on the node.", "Verify the private-network firewall permits TCP 22."],
        "automatic_safe": False,
        "requires_brain_review": True,
    },
    "repair-ssh-key-authorization": {
        "title": "Repair SSH key authorization",
        "actions": ["Compare the offered key fingerprint with the Brain-approved inventory.", "Repair authorized_keys permissions and retry key-only authentication."],
        "automatic_safe": False,
        "requires_brain_review": True,
    },
    "review-host-key-change": {
        "title": "Review SSH host identity change",
        "actions": ["Compare the presented host-key fingerprint with the node console.", "Replace the saved key only after the Brain approves the identity change."],
        "automatic_safe": False,
        "requires_brain_review": True,
    },
    "repair-brain-api-path": {
        "title": "Restore the Brain API path",
        "actions": ["Check Brain API health on the private network.", "Verify the node uses the configured Brain host and port."],
        "automatic_safe": True,
        "requires_brain_review": False,
    },
    "repair-github-credential-helper": {
        "title": "Repair GitHub credential storage",
        "actions": ["Verify the Git remote belongs to the expected GitHub account.", "Configure an OS-backed credential helper and authenticate interactively once."],
        "automatic_safe": False,
        "requires_brain_review": True,
    },
    "collect-expanded-diagnostics": {
        "title": "Collect expanded connectivity diagnostics",
        "actions": ["Capture channel, exit code, endpoint, and a redacted error summary.", "Submit the marker bundle to the Brain diagnostic queue."],
        "automatic_safe": True,
        "requires_brain_review": False,
    },
}


def connection_snapshot(
    local: bool = False,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return connections with freshness-aware effective status.

    Agents report a point-in-time status.  Without aging that report, a laptop
    which disappeared from the network continued to look online forever.
    ``reported_status`` retains the agent value while ``status`` is the value
    consumers should use for current dashboards and routing.
    """
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be at least 1")
    observed_at = now or datetime.now(UTC)
    cutoff = observed_at - timedelta(seconds=stale_after_seconds)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    source_machine_id, target_machine_id, channel, status,
                    latency_ms, last_checked_at, metadata, updated_at
                from machine_connections
                order by target_machine_id, channel
                """
            )
            rows = [dict(row) for row in cur.fetchall()]

    for row in rows:
        reported_status = str(row.get("status") or "unknown").strip().lower()
        checked_at = row.get("last_checked_at") or row.get("updated_at")
        is_stale = checked_at is None or checked_at < cutoff
        row["reported_status"] = reported_status
        row["is_stale"] = is_stale
        row["age_seconds"] = max(0.0, (observed_at - checked_at).total_seconds()) if checked_at else None
        row["status"] = "stale" if is_stale and reported_status in ONLINE_STATUSES else reported_status
        row["is_online"] = row["status"] in ONLINE_STATUSES
    return rows


def connection_summary(connections: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize effective connectivity without treating stale reports as live."""
    online = [row for row in connections if row.get("is_online")]
    stale = [row for row in connections if row.get("is_stale")]
    targets_online = {str(row["target_machine_id"]) for row in online if row.get("target_machine_id")}
    targets_reported = {str(row["target_machine_id"]) for row in connections if row.get("target_machine_id")}
    availability_checks = {
        "at_least_one_online_record": len(online) > 0,
        "at_least_one_online_target": len(targets_online) > 0,
    }
    diagnostics = connection_diagnostics(connections)
    return {
        "records": len(connections),
        "online_records": len(online),
        "stale_records": len(stale),
        "reported_targets": len(targets_reported),
        "online_targets": len(targets_online),
        "availability": {
            "status": "passed" if all(availability_checks.values()) else "failed",
            "rubric": availability_checks,
        },
        "diagnostics": diagnostics["summary"],
        "contract": {
            "version": 1,
            "freshness_aware": True,
            "effective_status_field": "status",
            "raw_status_field": "reported_status",
            "invariants": {
                "online_records_are_fresh": all(not bool(row.get("is_stale")) for row in online),
                "stale_online_reports_are_not_effectively_online": all(
                    not bool(row.get("is_online"))
                    for row in stale
                    if row.get("reported_status") in ONLINE_STATUSES
                ),
            },
        },
    }


def connection_diagnostics(
    connections: list[dict[str, Any]],
    target_machine_id: str | None = None,
    marker_codes: set[str] | None = None,
) -> dict[str, Any]:
    """Classify connection reports into stable, queryable diagnostic markers.

    Free-form stderr is used only for classification and is never returned. This
    keeps credentials or host details embedded in tool output out of API payloads.
    """
    markers: list[dict[str, Any]] = []
    for connection in connections:
        target = str(connection.get("target_machine_id") or "unknown")
        if target_machine_id and target != target_machine_id:
            continue
        markers.extend(_diagnostic_markers_for_connection(connection))

    if marker_codes:
        normalized_codes = {code.strip().upper() for code in marker_codes if code.strip()}
        markers = [marker for marker in markers if marker["code"] in normalized_codes]

    remediation_codes = sorted({code for marker in markers for code in marker["remediation_codes"]})
    severity_counts: dict[str, int] = {}
    code_counts: dict[str, int] = {}
    for marker in markers:
        severity_counts[marker["severity"]] = severity_counts.get(marker["severity"], 0) + 1
        code_counts[marker["code"]] = code_counts.get(marker["code"], 0) + 1
    return {
        "markers": markers,
        "remediations": {code: dict(REMEDIATION_CATALOG[code], code=code) for code in remediation_codes},
        "summary": {
            "marker_count": len(markers),
            "by_severity": severity_counts,
            "by_code": code_counts,
            "requires_brain_review": any(
                REMEDIATION_CATALOG[code]["requires_brain_review"] for code in remediation_codes
            ),
        },
        "contract": {
            "version": 1,
            "raw_error_text_exposed": False,
            "markers_are_deterministic": True,
            "privileged_remediation_requires_review": True,
        },
    }


def remediation_recommendations(marker_codes: list[str] | set[str]) -> list[dict[str, Any]]:
    """Return remediation records for marker codes without requiring DB access."""
    wanted = {
        POWERSHELL_MARKER_ALIASES.get(str(code).strip().upper(), str(code).strip().upper())
        for code in marker_codes
    }
    remediation_codes: set[str] = set()
    for rule in _DIAGNOSTIC_RULES:
        if rule["code"] in wanted:
            remediation_codes.update(rule["remediation_codes"])
    return [dict(REMEDIATION_CATALOG[code], code=code) for code in sorted(remediation_codes)]


def publish_connection_diagnostics(
    connections: list[dict[str, Any]] | None = None,
    target_machine_id: str | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """Publish marker events to the Brain listener with a five-minute dedupe key."""
    from .brain_bus import submit_listener_event

    diagnostic_set = connection_diagnostics(
        connections if connections is not None else connection_snapshot(local=local),
        target_machine_id=target_machine_id,
    )
    published: list[dict[str, Any]] = []
    priority_by_severity = {"critical": 95, "high": 85, "medium": 65, "low": 40}
    for marker in diagnostic_set["markers"]:
        result = submit_listener_event(
            source_type="machine",
            source_id=marker["target_machine_id"],
            event_type="connectivity_diagnostic",
            subject=f"Connectivity marker: {marker['code']}",
            body=(
                f"{marker['target_machine_id']} reported {marker['code']} "
                f"during {marker['stage']} on {marker['channel']}."
            ),
            priority=priority_by_severity.get(marker["severity"], 50),
            metadata={
                "machine_id": marker["target_machine_id"],
                "diagnostic_marker": marker,
                "remediation_codes": marker["remediation_codes"],
                "dedupe_key": marker["marker_id"],
                "dedupe_window_seconds": 300,
                "channel": "connectivity",
                "audit_kind": "connectivity_diagnostic",
            },
            local=local,
        )
        published.append({"marker_id": marker["marker_id"], **result})
    return {"diagnostics": diagnostic_set, "published": published}


def queue_diagnostic_query(
    target_machine_id: str,
    channels: list[str] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """Ask a node for bounded diagnostic evidence; never sends shell text."""
    from .brain_bus import create_speaker_message

    allowed_channels = {"tailscale-ping", "ssh-22", "brain-api", "github"}
    requested = sorted(set(channels or allowed_channels) & allowed_channels)
    if not target_machine_id.strip():
        raise ValueError("target_machine_id is required")
    correlation_id = f"connectivity-query:{target_machine_id}:{datetime.now(UTC).isoformat()}"
    message_id = create_speaker_message(
        target_id=target_machine_id,
        message_type="connectivity_diagnostic_query",
        subject="Brain connectivity diagnostic query",
        body="Run the governed connectivity probes and return structured marker evidence.",
        priority=75,
        metadata={
            "requested_channels": requested,
            "response_event_type": "connectivity_diagnostic",
            "correlation_id": correlation_id,
            "arbitrary_command_execution": False,
            "channel": "connectivity",
            "audit_kind": "diagnostic_query",
        },
        local=local,
    )
    return {"message_id": message_id, "target_machine_id": target_machine_id, "requested_channels": requested, "correlation_id": correlation_id}


def queue_diagnostic_response(
    target_machine_id: str,
    marker_codes: list[str],
    response_type: str = "remediation",
    release_ref: str | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """Send advisory remediation or a governed release notice to one node."""
    from .brain_bus import create_speaker_message

    if response_type not in {"remediation", "patch_notice", "status_update"}:
        raise ValueError("response_type must be remediation, patch_notice, or status_update")
    if response_type == "patch_notice" and not (release_ref or "").strip():
        raise ValueError("patch_notice requires release_ref")
    recommendations = remediation_recommendations(marker_codes)
    if not recommendations and response_type == "remediation":
        raise ValueError("no recognized diagnostic marker codes")
    if response_type == "patch_notice":
        body = f"A Brain-reviewed connectivity update is available as {release_ref}. Use the governed node updater."
    elif response_type == "status_update":
        body = "The Brain reviewed the connectivity markers; continue reporting structured status while review proceeds."
    else:
        body = "Brain remediation guidance: " + " ".join(
            f"{item['title']}: {' '.join(item['actions'])}" for item in recommendations
        )
    message_id = create_speaker_message(
        target_id=target_machine_id,
        message_type=f"connectivity_{response_type}",
        subject=f"Brain connectivity {response_type.replace('_', ' ')}",
        body=body,
        priority=85 if response_type == "patch_notice" else 70,
        metadata={
            "marker_codes": sorted({code.strip().upper() for code in marker_codes}),
            "remediations": recommendations,
            "release_ref": release_ref,
            "advisory_only": response_type != "patch_notice",
            "arbitrary_command_execution": False,
            "channel": "connectivity",
            "audit_kind": "diagnostic_response",
        },
        local=local,
    )
    return {"message_id": message_id, "target_machine_id": target_machine_id, "response_type": response_type}


_DIAGNOSTIC_RULES: tuple[dict[str, Any], ...] = (
    {"code": "SSH_HOST_KEY_MISMATCH", "category": "trust", "severity": "critical", "stage": "ssh_handshake", "channels": ("ssh",), "signals": ("remote host identification has changed", "host key verification failed"), "remediation_codes": ("review-host-key-change",)},
    {"code": "SSH_AUTH_FAILED", "category": "authentication", "severity": "high", "stage": "ssh_authentication", "channels": ("ssh",), "signals": ("permission denied", "publickey", "authentication failed", "no supported authentication"), "statuses": ("auth_failed",), "remediation_codes": ("repair-ssh-key-authorization",)},
    {"code": "SSH_PORT_BLOCKED", "category": "network", "severity": "high", "stage": "ssh_transport", "channels": ("ssh",), "signals": ("connection refused", "timed out", "timeout", "port 22", "actively refused"), "statuses": ("blocked", "refused", "timeout", "unreachable"), "remediation_codes": ("open-ssh-service-path",)},
    {"code": "TAILSCALE_UNREACHABLE", "category": "mesh", "severity": "high", "stage": "private_mesh", "channels": ("tailscale",), "statuses": tuple(FAILURE_STATUSES), "remediation_codes": ("restore-tailscale-path",)},
    {"code": "BRAIN_API_UNREACHABLE", "category": "control_plane", "severity": "high", "stage": "brain_api", "channels": ("brain-api", "api", "http"), "signals": ("connection refused", "timed out", "name resolution", "unreachable"), "statuses": tuple(FAILURE_STATUSES), "remediation_codes": ("repair-brain-api-path",)},
    {"code": "GITHUB_CREDENTIAL_REQUIRED", "category": "credentials", "severity": "medium", "stage": "source_update", "channels": ("github", "git"), "signals": ("could not read username", "authentication failed", "terminal prompts disabled", "credential", "403"), "remediation_codes": ("repair-github-credential-helper",)},
)

POWERSHELL_MARKER_ALIASES = {
    "SSH_PUBLIC_KEY_REJECTED": "SSH_AUTH_FAILED",
    "SSH_IDENTITY_MISSING": "SSH_AUTH_FAILED",
    "SSH_HOST_KEY_REJECTED": "SSH_HOST_KEY_MISMATCH",
    "SSH_SERVICE_NOT_LISTENING": "SSH_PORT_BLOCKED",
    "SSH_PORT_22_BLOCKED": "SSH_PORT_BLOCKED",
    "SSH_NETWORK_UNREACHABLE": "SSH_PORT_BLOCKED",
}


def _diagnostic_markers_for_connection(connection: dict[str, Any]) -> list[dict[str, Any]]:
    status = str(connection.get("status") or "unknown").strip().lower()
    channel = str(connection.get("channel") or "unknown").strip().lower()
    signal_text = " ".join(_metadata_signal_strings(connection.get("metadata"))).lower()
    matches: list[dict[str, Any]] = []

    if bool(connection.get("is_stale")) or status == "stale":
        matches.append({"code": "CONNECTION_REPORT_STALE", "category": "telemetry", "severity": "medium", "stage": "reporting", "remediation_codes": ("refresh-node-report",)})

    for rule in _DIAGNOSTIC_RULES:
        channel_match = any(fragment in channel for fragment in rule.get("channels", ()))
        signal_match = any(signal in signal_text for signal in rule.get("signals", ()))
        status_match = status in rule.get("statuses", ())
        if channel_match and (signal_match or status_match):
            matches.append(rule)

    if not matches and status in FAILURE_STATUSES:
        matches.append({"code": "CONNECTIVITY_FAILURE_UNCLASSIFIED", "category": "unknown", "severity": "medium", "stage": "connectivity", "remediation_codes": ("collect-expanded-diagnostics",)})

    target = str(connection.get("target_machine_id") or "unknown")
    source = str(connection.get("source_machine_id") or "unknown")
    return [
        {
            "marker_id": f"{target}:{channel}:{rule['code']}",
            "code": rule["code"],
            "category": rule["category"],
            "severity": rule["severity"],
            "stage": rule["stage"],
            "source_machine_id": source,
            "target_machine_id": target,
            "channel": channel,
            "status": status,
            "observed_at": connection.get("last_checked_at") or connection.get("updated_at"),
            "evidence": {"status": status, "channel": channel, "matched_error_text_redacted": bool(signal_text)},
            "remediation_codes": list(rule["remediation_codes"]),
        }
        for rule in matches
    ]


def _metadata_signal_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _metadata_signal_strings(nested)]
    if isinstance(value, (list, tuple, set)):
        return [item for nested in value for item in _metadata_signal_strings(nested)]
    return [str(value)] if value is not None else []


def _json_metadata(metadata: dict[str, Any] | None) -> str:
    import json

    return json.dumps(metadata or {})
