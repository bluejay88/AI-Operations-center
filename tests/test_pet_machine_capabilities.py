from pathlib import Path

import pytest

from ai_ops_center import api, pet_machine_capabilities as caps


ROOT = Path(__file__).resolve().parents[1]


def install_bus_mocks(monkeypatch):
    approvals = []
    speakers = []
    listeners = []
    rows = []
    monkeypatch.setattr(caps, "create_approval_request", lambda **kw: approvals.append(kw) or 41)
    monkeypatch.setattr(caps, "submit_listener_event", lambda **kw: listeners.append(kw) or {"event_id": 42, "actions": []})
    monkeypatch.setattr(caps, "create_speaker_message", lambda **kw: speakers.append(kw) or 43)
    monkeypatch.setattr(caps, "_record_request", lambda **kw: rows.append(kw))
    return approvals, listeners, speakers, rows


def test_browser_request_is_allow_checked_audited_and_held(monkeypatch):
    approvals, listeners, speakers, rows = install_bus_mocks(monkeypatch)
    result = caps.submit_capability_request(
        machine_id="research-laptop", pet_id="research-pet", capability_type="browser_navigation",
        payload={"url": "https://example.com/research"}, requester="jayla"
    )
    assert result["status"] == "pending_approval"
    assert result["approval_required"] is True
    assert result["worker_execution_authorized"] is False
    assert result["machine_receipt_id"] is None
    assert result["success_claimed"] is False
    assert len(approvals) == len(listeners) == len(speakers) == len(rows) == 1
    assert speakers[0]["message_type"] == "pet_capability_approval_hold"
    assert speakers[0]["metadata"]["executor"] == "approval_hold"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "https://localhost/x", "https://127.0.0.1/x", "https://user:pass@example.com/x", "https://example.com/x#secret"])
def test_browser_rejects_unsafe_scheme_host_credentials_and_fragment(url):
    with pytest.raises(ValueError):
        caps._validate_payload("browser_navigation", {"url": url})


def test_browser_honors_docker_domain_allowlist(monkeypatch):
    monkeypatch.setenv("PET_BROWSER_ALLOWED_DOMAINS", "openai.com,example.org")
    assert caps._validate_payload("browser_navigation", {"url": "https://docs.openai.com/x"})
    with pytest.raises(ValueError, match="outside the configured domain allowlist"):
        caps._validate_payload("browser_navigation", {"url": "https://example.com/x"})


def test_music_is_local_identifier_only_and_approval_held(monkeypatch):
    approvals, _, speakers, _ = install_bus_mocks(monkeypatch)
    result = caps.submit_capability_request(
        machine_id="business-laptop", pet_id="creative-pet", capability_type="music_playback",
        payload={"command": "play", "media_id": "focus-playlist-01"}, requester="jayla"
    )
    assert result["status"] == "pending_approval"
    assert result["worker_execution_authorized"] is False
    assert approvals and "DO NOT EXECUTE" in speakers[0]["body"]
    with pytest.raises(ValueError, match="safe local media_id"):
        caps._validate_payload("music_playback", {"command": "play", "media_id": "C:\\secret.mp3"})


def test_device_model_chat_targets_exact_pet_and_never_claims_completion(monkeypatch):
    approvals, _, speakers, rows = install_bus_mocks(monkeypatch)
    result = caps.submit_capability_request(
        machine_id="dev-laptop", pet_id="development-pet", capability_type="device_model_chat",
        payload={"prompt": "Summarize current build health.", "model_id": "ollama-local"}, requester="jayla"
    )
    assert approvals == []
    assert result["status"] == "requested"
    assert result["worker_execution_authorized"] is False
    assert result["success_claimed"] is False
    assert speakers[0]["metadata"]["execution_authorized"] is False
    assert speakers[0]["metadata"]["receipt_required_for_completion"] is True
    assert rows[0]["approval_request_id"] is None


def test_wrong_pet_machine_pair_fails_before_any_bus_write(monkeypatch):
    approvals, listeners, speakers, rows = install_bus_mocks(monkeypatch)
    with pytest.raises(ValueError, match="not assigned"):
        caps.submit_capability_request(
            machine_id="research-laptop", pet_id="creative-pet", capability_type="device_model_chat",
            payload={"prompt": "hello"}, requester="jayla"
        )
    assert approvals == listeners == speakers == rows == []


def test_api_contract_and_request_routes_are_connected():
    paths = {route.path: route.methods for route in api.app.routes if route.path.startswith("/pet-machine-capabilities")}
    assert paths["/pet-machine-capabilities/contracts"] == {"GET"}
    assert paths["/pet-machine-capabilities/requests"] == {"POST"}
    assert paths["/pet-machine-capabilities/requests/{request_id}/dispatch"] == {"POST"}
    assert paths["/pet-machine-capabilities/requests/{request_id}"] == {"GET"}
    assert paths["/pet-machine-capabilities/receipts"] == {"POST"}


def test_migration_015_persists_append_only_requests_without_success_status():
    sql = (ROOT / "sql" / "migrations" / "015_pet_machine_capability_requests.sql").read_text(encoding="utf-8")
    assert "before update or delete" in sql
    assert "speaker_message_id bigint not null" in sql
    assert "listener_event_id bigint not null" in sql
    assert "approval_request_id is not null" in sql
    assert "completed" not in sql


def test_dispatch_rejects_unapproved_remote_action(monkeypatch):
    monkeypatch.setenv("PET_CAPABILITY_SIGNING_KEY", "k" * 32)
    monkeypatch.setattr(caps, "_load_request", lambda *a, **k: {"request_id": "00000000-0000-0000-0000-000000000001", "machine_id": "research-laptop", "pet_id": "research-pet", "capability_type": "browser_navigation", "payload": {"url": "https://example.com"}, "approval_request_id": 1, "approval_status": "pending"})
    with pytest.raises(PermissionError, match="not approved"):
        caps.dispatch_approved_request("00000000-0000-0000-0000-000000000001", "brain")


def test_approved_dispatch_is_signed_but_not_success(monkeypatch):
    monkeypatch.setenv("PET_CAPABILITY_SIGNING_KEY", "k" * 32)
    request = {"request_id": "00000000-0000-0000-0000-000000000001", "machine_id": "research-laptop", "pet_id": "research-pet", "capability_type": "browser_navigation", "payload": {"url": "https://example.com"}, "approval_request_id": 1, "approval_status": "approved"}
    sent = []
    monkeypatch.setattr(caps, "_load_request", lambda *a, **k: request)
    monkeypatch.setattr(caps, "create_speaker_message", lambda **kw: sent.append(kw) or 91)
    monkeypatch.setattr(caps, "_record_dispatch", lambda **kw: None)
    result = caps.dispatch_approved_request(request["request_id"], "brain")
    assert len(sent[0]["metadata"]["signature"]) == 64
    assert sent[0]["metadata"]["execution_authorized"] is True
    assert result["success_claimed"] is False and result["machine_receipt_id"] is None


def test_machine_executor_is_disabled_by_default_and_detects_tampering():
    key = "k" * 32
    envelope = {"contract_version": "pet-machine-execution-v1", "request_id": "r1", "machine_id": "dev-laptop", "pet_id": "development-pet", "capability_type": "device_model_chat", "payload": {"prompt": "hi"}, "execution_authorized": True}
    envelope["signature"] = caps._sign(envelope, key.encode())
    executor = caps.MachineCapabilityExecutor("dev-laptop", signing_key=key)
    receipt = executor.execute(envelope)
    assert receipt["status"] == "held"
    assert "no action ran" in receipt["detail"]
    tampered = envelope | {"machine_id": "research-laptop"}
    with pytest.raises(PermissionError, match="signature"):
        executor.execute(tampered)


def test_enabled_machine_handler_produces_signed_machine_report_only():
    key = "k" * 32
    envelope = {"contract_version": "pet-machine-execution-v1", "request_id": "r1", "machine_id": "dev-laptop", "pet_id": "development-pet", "capability_type": "device_model_chat", "payload": {"prompt": "hi"}, "execution_authorized": True}
    envelope["signature"] = caps._sign(envelope, key.encode())
    executor = caps.MachineCapabilityExecutor("dev-laptop", model_handler=lambda payload: "local answer", enable_model_chat=True, signing_key=key)
    receipt = executor.execute(envelope)
    assert receipt["status"] == "completed"
    assert len(receipt["signature"]) == 64


def test_migration_016_persists_append_only_dispatch_and_receipts():
    sql = (ROOT / "sql" / "migrations" / "016_pet_machine_capability_dispatch.sql").read_text(encoding="utf-8")
    assert "pet_machine_capability_dispatches" in sql
    assert "pet_machine_capability_receipts" in sql
    assert sql.count("before update or delete") == 2
