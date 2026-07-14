from __future__ import annotations

import hashlib
import base64
import json
import os
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .db import ROOT, connect
from .pet_instruction_protocol import PostgresReplayGuard, sign_instruction, verify_instruction
from .remote_ops import request_remote_operation
from .settings import get_settings


CONFIG_PATH = ROOT / "config" / "ssh_nodes.yaml"
KILL_SWITCH_PATH = ROOT / "state" / "ssh-broker.disabled"
MAX_OUTPUT_BYTES = 65_536
COMMANDS: dict[str, dict[str, Any]] = {
    "hostname": {"arguments": 0},
    "service-status": {"arguments": 1, "values": {"sshd", "tailscale", "docker", "com.docker.service"}},
    "disk-health": {"arguments": 0},
    "app-version": {"arguments": 0},
    "git-status": {"arguments": 0},
    "docker-status": {"arguments": 0},
    "event-log-summary": {"arguments": 0},
    "worker-health": {"arguments": 0},
}
_SAFE_ARGUMENT = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REDACTIONS = (
    re.compile(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)


def request_ssh_diagnostic(
    machine_id: str,
    command_id: str,
    arguments: list[str],
    requested_by: str,
    priority: int = 80,
    *,
    local: bool = False,
) -> dict[str, Any]:
    normalized = validate_command(command_id, arguments)
    return request_remote_operation(
        machine_id=machine_id,
        requested_by=requested_by,
        operation_type="ssh_diagnostic",
        command_summary=f"Run allowlisted SSH diagnostic '{command_id}' on {machine_id}.",
        priority=priority,
        metadata={"command_id": command_id, "arguments": normalized, "broker_schema": "ai-ops.ssh-broker.v1"},
        local=local,
    )


def validate_command(command_id: str, arguments: list[str]) -> list[str]:
    policy = COMMANDS.get(command_id)
    if policy is None:
        raise ValueError("command_id is not in the SSH diagnostic allowlist")
    normalized = [str(value) for value in arguments]
    if len(normalized) != int(policy["arguments"]):
        raise ValueError(f"{command_id} requires exactly {policy['arguments']} arguments")
    if any(not _SAFE_ARGUMENT.fullmatch(value) for value in normalized):
        raise ValueError("diagnostic argument failed validation")
    allowed_values = policy.get("values")
    if allowed_values and any(value not in allowed_values for value in normalized):
        raise ValueError("diagnostic argument is not in the command allowlist")
    return normalized


def execute_approved_diagnostic(operation_id: int, executed_by: str, *, local: bool = False) -> dict[str, Any]:
    if KILL_SWITCH_PATH.exists():
        raise PermissionError("SSH broker fleet kill switch is active")
    operation, approval = _load_approved_operation(operation_id, local=local)
    metadata = dict(operation.get("metadata") or {})
    command_id = str(metadata.get("command_id") or "")
    arguments = validate_command(command_id, list(metadata.get("arguments") or []))
    target = _target_config(str(operation["machine_id"]))
    _validate_target_files(target)

    settings = get_settings()
    signing_secret = settings.brain_instruction_secret.encode("utf-8")
    now = datetime.now(UTC)
    unsigned = {
        "instruction_id": f"ssh-exec-{uuid.uuid4()}",
        "nonce": f"ssh-nonce-{uuid.uuid4()}",
        "signer_id": "brain-gaming-pc",
        "target_machine_id": str(operation["machine_id"]),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "payload": {
            "operation_id": int(operation["id"]),
            "approval_request_id": int(approval["id"]),
            "command_id": command_id,
            "arguments": arguments,
        },
    }
    envelope = sign_instruction(unsigned, signing_secret)
    decision = verify_instruction(
        envelope,
        expected_machine_id=str(operation["machine_id"]),
        secret_for_signer=lambda signer: signing_secret if signer == "brain-gaming-pc" else None,
        replay_guard=PostgresReplayGuard(local=local),
    )
    if not decision.accepted:
        raise PermissionError(f"signed diagnostic envelope was rejected: {decision.code}")

    execution_id = uuid.uuid4()
    remote_command = " ".join(["aiops-diagnostic", command_id, *arguments])
    ssh_args = [
        "ssh", "-F", "NUL", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={target['known_hosts_file']}", "-o", "IdentitiesOnly=yes",
        "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=8", "-i", target["identity_file"],
        f"{target['user']}@{target['host']}", remote_command,
    ]
    started = time.monotonic()
    status = "failed"
    exit_code: int | None = None
    output = ""
    try:
        completed = subprocess.run(ssh_args, capture_output=True, text=True, timeout=30, shell=False, check=False)
        exit_code = completed.returncode
        output = (completed.stdout or "") + (completed.stderr or "")
        status = "completed" if exit_code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        status = "timed_out"
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "") + ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    redacted = _redact(output.encode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"))
    _record_execution(
        execution_id=execution_id,
        operation=operation,
        approval=approval,
        executed_by=executed_by,
        command_id=command_id,
        arguments=arguments,
        envelope_sha256=str(decision.verified_envelope_sha256),
        target=target,
        status=status,
        exit_code=exit_code,
        output=redacted,
        duration_ms=duration_ms,
        local=local,
    )
    return {
        "execution_id": str(execution_id),
        "operation_id": operation_id,
        "machine_id": operation["machine_id"],
        "command_id": command_id,
        "status": status,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "output": redacted,
    }


def set_kill_switch(disabled: bool, actor: str, reason: str) -> dict[str, Any]:
    if len(reason.strip()) < 8:
        raise ValueError("kill-switch changes require an evidence-rich reason")
    KILL_SWITCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    if disabled:
        KILL_SWITCH_PATH.write_text(
            json.dumps({"disabled_at": datetime.now(UTC).isoformat(), "actor": actor, "reason": reason}, sort_keys=True),
            encoding="utf-8",
        )
    elif KILL_SWITCH_PATH.exists():
        KILL_SWITCH_PATH.unlink()
    return {"disabled": KILL_SWITCH_PATH.exists(), "actor": actor, "reason": reason}


def broker_status() -> dict[str, Any]:
    config = _load_config()
    targets = {}
    for machine_id, raw in dict(config.get("targets") or {}).items():
        target = _target_config(machine_id, config=config)
        targets[machine_id] = {
            "host": target["host"],
            "user": target["user"],
            "identity_present": Path(target["identity_file"]).is_file(),
            "known_hosts_present": Path(target["known_hosts_file"]).is_file(),
            "host_key_pinned": bool(target["host_key_fingerprint"]),
        }
    return {"disabled": KILL_SWITCH_PATH.exists(), "commands": sorted(COMMANDS), "targets": targets}


def _load_approved_operation(operation_id: int, *, local: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select * from remote_operation_requests where id = %s", (operation_id,))
            operation_row = cur.fetchone()
            if not operation_row:
                raise ValueError(f"remote operation {operation_id} was not found")
            operation = dict(operation_row)
            approval_id = int(dict(operation.get("metadata") or {}).get("approval_request_id") or 0)
            cur.execute("select * from approval_requests where id = %s", (approval_id,))
            approval_row = cur.fetchone()
    if operation.get("operation_type") != "ssh_diagnostic":
        raise PermissionError("only typed SSH diagnostic operations may enter this broker")
    if not approval_row or approval_row.get("status") != "approved":
        raise PermissionError("SSH diagnostic requires an approved human approval record")
    return operation, dict(approval_row)


def _load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _target_config(machine_id: str, *, config: dict[str, Any] | None = None) -> dict[str, str]:
    resolved = config or _load_config()
    raw = dict((resolved.get("targets") or {}).get(machine_id) or {})
    if not raw:
        raise ValueError(f"SSH target {machine_id!r} is not configured")
    return {
        "host": str(raw.get("host") or ""),
        "user": str(raw.get("user") or ""),
        "identity_file": str(Path(os.path.expanduser(str(raw.get("identity_file") or ""))).resolve()),
        "known_hosts_file": str(Path(os.path.expanduser(str(resolved.get("known_hosts_file") or ""))).resolve()),
        "host_key_fingerprint": str(raw.get("host_key_fingerprint") or ""),
    }


def _validate_target_files(target: dict[str, str]) -> None:
    if target["user"] != "aiops-diagnostic":
        raise PermissionError("SSH broker target must use the non-administrator aiops-diagnostic account")
    if not target["host_key_fingerprint"].startswith("SHA256:"):
        raise PermissionError("SSH target has no out-of-band verified host-key fingerprint")
    for name in ("identity_file", "known_hosts_file"):
        if not Path(target[name]).is_file():
            raise PermissionError(f"SSH broker {name} is missing")


def _record_execution(**values: Any) -> None:
    local = bool(values.pop("local"))
    operation = values["operation"]
    approval = values["approval"]
    arguments_json = json.dumps(values["arguments"], sort_keys=True, separators=(",", ":"))
    output = values["output"]
    identity_public = Path(values["target"]["identity_file"] + ".pub")
    identity_fingerprint = _openssh_public_fingerprint(identity_public) if identity_public.is_file() else "missing"
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into ssh_broker_executions (
                    execution_id, remote_operation_request_id, approval_request_id, target_machine_id,
                    requested_by, executed_by, command_id, arguments_sha256, envelope_sha256,
                    host_key_fingerprint, identity_public_fingerprint, status, exit_code,
                    output_sha256, redacted_output, duration_ms, metadata
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(values["execution_id"]), operation["id"], approval["id"], operation["machine_id"],
                    operation["requested_by"], values["executed_by"], values["command_id"],
                    _sha256(arguments_json.encode()), values["envelope_sha256"], values["target"]["host_key_fingerprint"],
                    identity_fingerprint, values["status"], values["exit_code"], _sha256(output.encode()), output,
                    values["duration_ms"], json.dumps({"output_truncated_at_bytes": MAX_OUTPUT_BYTES}),
                ),
            )
            cur.execute(
                "update remote_operation_requests set status = %s, completed_at = now(), updated_at = now() where id = %s",
                ("completed" if values["status"] == "completed" else "failed", operation["id"]),
            )
        conn.commit()


def _redact(value: str) -> str:
    redacted = value
    for pattern in _REDACTIONS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _openssh_public_fingerprint(path: Path) -> str:
    parts = path.read_text(encoding="ascii").strip().split()
    if len(parts) < 2:
        raise ValueError("SSH public identity is malformed")
    key_blob = base64.b64decode(parts[1], validate=True)
    digest = base64.b64encode(hashlib.sha256(key_blob).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"
