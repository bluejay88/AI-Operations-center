from pathlib import Path

import pytest

from ai_ops_center import ssh_broker


def test_diagnostic_command_catalog_rejects_shell_text_and_unknown_operations():
    assert ssh_broker.validate_command("hostname", []) == []
    assert ssh_broker.validate_command("service-status", ["sshd"]) == ["sshd"]
    with pytest.raises(ValueError):
        ssh_broker.validate_command("service-status", ["sshd;whoami"])
    with pytest.raises(ValueError):
        ssh_broker.validate_command("powershell", ["Get-Process"])


def test_ssh_execution_is_pinned_noninteractive_and_never_uses_a_shell():
    source = Path(ssh_broker.__file__).read_text(encoding="utf-8")
    assert '"StrictHostKeyChecking=yes"' in source
    assert '"BatchMode=yes"' in source
    assert '"ClearAllForwardings=yes"' in source
    assert "shell=False" in source
    assert "accept-new" not in source


def test_worker_sshd_setup_is_brain_only_nonadmin_and_forced_command():
    root = Path(__file__).resolve().parents[1]
    setup = (root / "docker" / "setup-worker-openssh-tailscale-admin.ps1").read_text(encoding="utf-8")
    command = (root / "docker" / "ssh-diagnostic-command.ps1").read_text(encoding="utf-8")
    assert 'AllowedRemoteAddress = "100.70.49.32/32"' in setup
    assert 'UserName = "aiops-diagnostic"' in setup
    assert '"AllowTcpForwarding" -Value "no"' in setup
    assert '"AllowAgentForwarding" -Value "no"' in setup
    assert '"PermitTTY" -Value "no"' in setup
    assert '"ForceCommand"' in setup
    assert "administrators_authorized_keys" in setup
    assert "Add-Content -Path $adminAuthorizedKeys" not in setup
    assert "$env:SSH_ORIGINAL_COMMAND" in command
    assert "Invoke-Expression" not in command


def test_automation_never_uses_trust_on_first_use():
    root = Path(__file__).resolve().parents[1]
    scripts = [
        root / "docker" / "test-brain-to-laptops.ps1",
        root / "docker" / "test-brain-ssh-and-api.ps1",
        root / "docker" / "audit-laptop-unblock.ps1",
    ]
    for script in scripts:
        source = script.read_text(encoding="utf-8")
        assert "StrictHostKeyChecking=yes" in source
        assert "accept-new" not in source
