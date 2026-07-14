from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_brain_probe_never_auto_accepts_host_keys_and_is_bounded():
    source = (ROOT / "docker" / "test-brain-to-laptops.ps1").read_text(encoding="utf-8")

    assert '"StrictHostKeyChecking=yes"' in source
    assert "StrictHostKeyChecking=accept-new" not in source
    assert "Test-TcpPort" in source
    assert "ConnectionAttempts=1" in source


def test_unknown_host_key_is_reported_without_becoming_trusted():
    probe = (ROOT / "docker" / "test-brain-to-laptops.ps1").read_text(encoding="utf-8")
    library = (ROOT / "docker" / "lib.ps1").read_text(encoding="utf-8")

    assert 'return "SSH_HOST_KEY_UNVERIFIED"' in library
    assert "Get-PresentedHostKeyFingerprint" in probe
    assert "presented_host_key_fingerprint" in probe
    assert "host_key_trusted = $false" in probe
    assert "ssh-keyscan" in probe
    assert "known_hosts or grant trust" in probe
