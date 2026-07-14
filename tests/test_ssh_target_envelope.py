from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="target broker is Windows OpenSSH specific")


def _command(key: str, machine_id: str = "dev-laptop") -> str:
    now = int(time.time())
    envelope = {
        "schema": "ai-ops.ssh-envelope.v1",
        "target_machine_id": machine_id,
        "command_id": "hostname",
        "arguments": [],
        "nonce": f"ssh-nonce-{uuid.uuid4()}",
        "issued_at": now,
        "expires_at": now + 300,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(key.encode(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"aiops-diagnostic-v1 {encoded} {signature}"


def _run(script: Path, program_data: Path, original_command: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "ProgramData": str(program_data), "SSH_ORIGINAL_COMMAND": original_command}
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        check=False,
    )


def test_target_verifies_signature_target_expiry_and_durable_nonce(tmp_path: Path) -> None:
    root = tmp_path / "AI-Ops"
    root.mkdir()
    key = "target-specific-test-key-" + "x" * 32
    (root / "ssh-broker-envelope-key").write_text(key, encoding="ascii")
    (root / "machine-id").write_text("dev-laptop", encoding="ascii")
    script = Path(__file__).parents[1] / "docker" / "ssh-diagnostic-command.ps1"

    signed = _command(key)
    accepted = _run(script, tmp_path, signed)
    assert accepted.returncode == 0, accepted.stderr + accepted.stdout
    assert json.loads(accepted.stdout)["status"] == "ok"

    replayed = _run(script, tmp_path, signed)
    assert replayed.returncode == 64
    assert json.loads(replayed.stdout)["status"] == "denied"

    wrong_target = _run(script, tmp_path, _command(key, "research-laptop"))
    assert wrong_target.returncode == 64
    tampered = signed[:-1] + ("0" if signed[-1] != "0" else "1")
    assert _run(script, tmp_path, tampered).returncode == 64
