"""Second-pass independent security characterization for PET machine execution.

Passing tests capture remediated controls.  Strict xfails are explicit release
blockers and should become ordinary passing tests before executor enablement.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
import inspect
from pathlib import Path
import uuid

import pytest

from ai_ops_center import pet_machine_capabilities as caps


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DISPATCH_KEY = "research-dispatch-key-material-at-least-32-bytes"
RESEARCH_RECEIPT_KEY = "research-receipt-key-material-at-least-32-bytes"
DEV_DISPATCH_KEY = "dev-dispatch-key-material-at-least-32-bytes"
REQUEST_ID = "00000000-0000-0000-0000-000000000201"


def _envelope(key: str = RESEARCH_DISPATCH_KEY) -> dict:
    now = datetime.now(UTC)
    value = {
        "contract_version": "pet-machine-execution-v1",
        "request_id": REQUEST_ID,
        "machine_id": "research-laptop",
        "pet_id": "research-pet",
        "capability_type": "device_model_chat",
        "executor": "device_model_chat",
        "payload": {"prompt": "bounded review probe"},
        "approval_request_id": None,
        "approval_status": None,
        "dispatched_by": "brain-principal",
        "key_id": "dispatch:research-laptop:v1",
        "nonce": str(uuid.uuid4()),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "execution_authorized": True,
        "receipt_required_for_completion": True,
    }
    value["dispatch_sha256"] = caps._payload_sha256(value)
    value["signature"] = caps._sign(value, key.encode())
    return value


def test_second_pass_directional_machine_key_isolation(monkeypatch):
    monkeypatch.setenv("PET_DISPATCH_VERIFY_KEY_RESEARCH_LAPTOP", RESEARCH_DISPATCH_KEY)
    monkeypatch.setenv("PET_RECEIPT_SIGNING_KEY_RESEARCH_LAPTOP", RESEARCH_RECEIPT_KEY)
    executor = caps.MachineCapabilityExecutor(
        "research-laptop",
        model_handler=lambda _: "ok",
        enable_model_chat=True,
    )
    with pytest.raises(PermissionError, match="signature"):
        executor.execute(_envelope(DEV_DISPATCH_KEY))


def test_second_pass_effective_receipt_uniqueness_is_declared():
    sql = (ROOT / "sql" / "migrations" / "017_harden_pet_machine_capability_dispatch.sql").read_text(
        encoding="utf-8"
    ).lower()
    assert "unique index" in sql
    assert "on pet_machine_capability_receipts(request_id, machine_id)" in sql


def test_second_pass_dispatch_intent_is_reserved_before_publish():
    source = inspect.getsource(caps.dispatch_approved_request)
    assert "_publish_dispatch_outbox" in source
    migration = (ROOT / "sql" / "migrations" / "018_pet_machine_capability_runtime_authority.sql").read_text(
        encoding="utf-8"
    ).lower()
    assert "publish_pet_machine_capability_dispatch" in migration
    assert "pet_machine_capability_dispatch_intents" in migration


def test_second_pass_replay_is_rejected_across_executor_restart():
    calls: list[dict] = []
    consumed: set[tuple[str, str]] = set()
    class DurableGuard:
        def consume(self, **values):
            identity = (values["machine_id"], values["nonce"])
            if identity in consumed:
                return False
            consumed.add(identity)
            return True
    envelope = _envelope()
    first = caps.MachineCapabilityExecutor(
        "research-laptop",
        model_handler=lambda payload: calls.append(payload) or "ok",
        enable_model_chat=True,
        signing_key=RESEARCH_DISPATCH_KEY,
        receipt_signing_key=RESEARCH_RECEIPT_KEY,
        replay_guard=DurableGuard(),
    )
    second = caps.MachineCapabilityExecutor(
        "research-laptop",
        model_handler=lambda payload: calls.append(payload) or "ok",
        enable_model_chat=True,
        signing_key=RESEARCH_DISPATCH_KEY,
        receipt_signing_key=RESEARCH_RECEIPT_KEY,
        replay_guard=DurableGuard(),
    )
    assert first.execute(envelope)["status"] == "completed"
    assert second.execute(envelope)["status"] == "held"
    assert len(calls) == 1


def test_second_pass_dispatch_actor_is_derived_from_authentication():
    tree = ast.parse((ROOT / "ai_ops_center" / "api.py").read_text(encoding="utf-8"))
    dispatch_model = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PetMachineCapabilityDispatchRequest"
    )
    body_fields = {
        node.target.id
        for node in dispatch_model.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "actor" not in body_fields


def test_second_pass_publish_uses_transactional_outbox():
    migration = (ROOT / "sql" / "migrations" / "018_pet_machine_capability_runtime_authority.sql").read_text(
        encoding="utf-8"
    ).lower()
    source = inspect.getsource(caps.dispatch_approved_request).lower()
    assert "outbox" in migration
    assert "idempotency" in source


def test_second_pass_directional_keys_have_lifecycle_authority():
    migration = (ROOT / "sql" / "migrations" / "018_pet_machine_capability_runtime_authority.sql").read_text(
        encoding="utf-8"
    ).lower()
    assert "pet_machine_capability_keys" in migration
    assert "revoked_at" in migration
    assert "not_before" in migration
    assert "not_after" in migration
