"""Independent security characterization for the PET machine capability lane.

Passing tests preserve verified safeguards. Strict xfails are release blockers:
they document behavior that must change before the lane can be enabled.
"""

from pathlib import Path
from datetime import UTC, datetime, timedelta
import uuid

import pytest

from ai_ops_center import pet_machine_capabilities as caps


ROOT = Path(__file__).resolve().parents[1]
KEY = "review-key-material-at-least-32-bytes"
REQUEST_ID = "00000000-0000-0000-0000-000000000101"


def _request(capability="browser_navigation", approval_status="approved"):
    payload = {"url": "https://example.com"} if capability == "browser_navigation" else {"prompt": "hello"}
    return {
        "request_id": REQUEST_ID,
        "machine_id": "research-laptop",
        "pet_id": "research-pet",
        "capability_type": capability,
        "payload": payload,
        "approval_request_id": 41 if capability == "browser_navigation" else None,
        "approval_status": approval_status,
    }


def _execution(**overrides):
    now = datetime.now(UTC)
    value = {
        "contract_version": "pet-machine-execution-v1",
        "key_id": "dispatch:research-laptop:v1",
        "request_id": REQUEST_ID,
        "machine_id": "research-laptop",
        "pet_id": "research-pet",
        "capability_type": "browser_navigation",
        "executor": "browser_navigation",
        "payload": {"url": "https://example.com"},
        "approval_request_id": 41,
        "approval_status": "approved",
        "execution_authorized": True,
        "receipt_required_for_completion": True,
        "key_id": "dispatch:research-laptop:v1",
        "nonce": str(uuid.uuid4()),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    }
    value.update(overrides)
    value["executor"] = caps.WORKER_EXECUTORS.get(value["capability_type"], {}).get("executor")
    value["dispatch_sha256"] = caps._payload_sha256(value)
    value["signature"] = caps._sign(value, KEY.encode())
    return value


@pytest.fixture(autouse=True)
def review_browser_allowlist(monkeypatch):
    monkeypatch.setenv("PET_BROWSER_ALLOWED_DOMAINS", "example.com")


def _receipt(**overrides):
    value = {
        "contract_version": "pet-machine-receipt-v1",
        "request_id": REQUEST_ID,
        "machine_id": "research-laptop",
        "pet_id": "research-pet",
        "capability_type": "browser_navigation",
        "status": "completed",
        "detail": "reported complete",
    }
    value.update(overrides)
    value["signature"] = caps._sign(value, KEY.encode())
    return value


def test_review_preserves_target_binding_tamper_detection_and_disabled_default():
    executor = caps.MachineCapabilityExecutor("research-laptop", signing_key=KEY)
    held = executor.execute(_execution())
    assert held["status"] == "held"
    tampered = _execution(machine_id="dev-laptop")
    with pytest.raises(PermissionError):
        executor.execute(tampered)


def test_review_preserves_authoritative_approval_check_before_dispatch(monkeypatch):
    monkeypatch.setenv("PET_DISPATCH_SIGNING_KEY_RESEARCH_LAPTOP", KEY)
    monkeypatch.setattr(caps, "_load_request", lambda *a, **k: _request(approval_status="pending"))
    with pytest.raises(PermissionError, match="not approved"):
        caps.dispatch_approved_request(REQUEST_ID, "caller-asserted-actor")


def test_review_preserves_missing_key_fail_closed(monkeypatch):
    monkeypatch.delenv("PET_CAPABILITY_SIGNING_KEY", raising=False)
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        caps._signing_key()


def test_review_requires_exactly_once_execution_for_replayed_signed_envelope():
    calls = []
    executor = caps.MachineCapabilityExecutor(
        "research-laptop",
        browser_handler=lambda payload: calls.append(payload) or "opened",
        enable_browser=True,
        signing_key=KEY,
    )
    envelope = _execution()
    assert executor.execute(envelope)["status"] == "completed"
    assert executor.execute(envelope)["status"] == "held"
    assert len(calls) == 1


def test_review_requires_executor_to_reject_pending_remote_approval():
    executor = caps.MachineCapabilityExecutor(
        "research-laptop", browser_handler=lambda _: "opened", enable_browser=True, signing_key=KEY
    )
    with pytest.raises(PermissionError):
        executor.execute(_execution(approval_status="pending"))


def test_review_requires_target_side_url_validation():
    calls = []
    executor = caps.MachineCapabilityExecutor(
        "research-laptop",
        browser_handler=lambda payload: calls.append(payload) or "opened",
        enable_browser=True,
        signing_key=KEY,
    )
    receipt = executor.execute(_execution(payload={"url": "https://127.0.0.1/admin"}))
    assert receipt["status"] == "held"
    assert calls == []


@pytest.mark.parametrize("url", ["https://2130706433/", "https://0x7f000001/", "https://0177.0.0.1/"])
def test_review_requires_alternate_loopback_forms_to_be_rejected(url):
    with pytest.raises(ValueError):
        caps._validate_url(url)


def test_review_requires_browser_domain_allowlist_to_fail_closed(monkeypatch):
    monkeypatch.delenv("PET_BROWSER_ALLOWED_DOMAINS", raising=False)
    with pytest.raises(RuntimeError):
        caps._validate_url("https://example.com/path")


def test_review_requires_per_machine_key_isolation():
    research_executor = caps.MachineCapabilityExecutor("research-laptop", signing_key=KEY, enable_model_chat=True, model_handler=lambda _: "ok")
    forged_by_other_machine = _execution(
        capability_type="device_model_chat",
        payload={"prompt": "run"},
        approval_request_id=None,
        approval_status=None,
    )
    forged_by_other_machine["signature"] = caps._sign(
        {name: value for name, value in forged_by_other_machine.items() if name != "signature"},
        b"dev-machine-directional-key-material-32bytes",
    )
    with pytest.raises(PermissionError):
        research_executor.execute(forged_by_other_machine)


def test_review_requires_receipt_to_match_capability_and_dispatch(monkeypatch):
    monkeypatch.setenv("PET_CAPABILITY_SIGNING_KEY", KEY)
    monkeypatch.setattr(caps, "_load_request", lambda *a, **k: _request("browser_navigation"))
    monkeypatch.setattr(caps, "submit_listener_event", lambda **k: {"event_id": 1})
    monkeypatch.setattr(caps, "_record_receipt", lambda **k: 2)
    with pytest.raises(PermissionError):
        caps.record_machine_receipt(_receipt(capability_type="device_model_chat"))


def test_review_requires_dispatch_before_completed_receipt(monkeypatch):
    monkeypatch.setenv("PET_CAPABILITY_SIGNING_KEY", KEY)
    monkeypatch.setattr(caps, "_load_request", lambda *a, **k: _request())
    monkeypatch.setattr(caps, "submit_listener_event", lambda **k: {"event_id": 1})
    monkeypatch.setattr(caps, "_record_receipt", lambda **k: 2)
    with pytest.raises(PermissionError):
        caps.record_machine_receipt(_receipt())


def test_review_requires_dispatch_side_effect_idempotency(monkeypatch):
    monkeypatch.setenv("PET_DISPATCH_SIGNING_KEY_RESEARCH_LAPTOP", KEY)
    monkeypatch.setattr(caps, "_load_request", lambda *a, **k: _request())
    sent = []
    monkeypatch.setattr(caps, "create_speaker_message", lambda **k: sent.append(k) or len(sent))
    monkeypatch.setattr(caps, "_record_dispatch", lambda **k: None)
    caps.dispatch_approved_request(REQUEST_ID, "brain")
    caps.dispatch_approved_request(REQUEST_ID, "brain")
    assert len(sent) == 1


def test_review_requires_database_receipt_idempotency_contract():
    # Migration 016 is already applied and immutable; 017 must supersede its
    # ineffective key without rewriting historical bytes.
    sql = (ROOT / "sql" / "migrations" / "017_harden_pet_machine_capability_dispatch.sql").read_text(encoding="utf-8").lower()
    assert "unique index" in sql or "create unique index" in sql
    assert "on pet_machine_capability_receipts(request_id, machine_id)" in sql
    assert "unique(request_id, machine_id, id)" not in sql


def test_review_requires_worker_integration_before_runtime_release():
    worker = (ROOT / "ai_ops_center" / "worker.py").read_text(encoding="utf-8")
    assert "pet_capability_signed_execution" in worker
    assert "MachineCapabilityExecutor" in worker
