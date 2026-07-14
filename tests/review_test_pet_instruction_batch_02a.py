"""Independent negative-characterization tests for PET instruction batch 02A.

These tests are review evidence, not implementation acceptance. Strict xfails
describe security gates the current implementation does not yet satisfy.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ai_ops_center.pet_capability_certification import evaluate_capability_batch, sha256_file
from ai_ops_center.pet_instruction_protocol import InMemoryReplayGuard, verify_instruction
from ai_ops_center import worker


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 13, 20, 30, tzinfo=timezone.utc)
SECRET = b"independent-review-secret-at-least-32-bytes"


def _apparently_complete_submission():
    artifact = ROOT / "ai_ops_center" / "pet_instruction_protocol.py"
    return {
        "feature_ids": ["PET-02-04", "PET-02-05", "PET-02-06", "PET-02-07", "PET-02-08"],
        "implementation_owner": "protocol-engineer",
        "artifacts": [{"path": "ai_ops_center/pet_instruction_protocol.py", "sha256": sha256_file(artifact)}],
        "tests": {"passed": 999, "failed": 0, "report": "does-not-exist.xml"},
        "physical_evidence": {
            "task_id": 900001,
            "listener_event_id": 900002,
            "peer_request_id": 900003,
            "producer_machine_id": "invented-laptop",
        },
        "reviewed_by": ["rubric-auditor", "security-monitor"],
        "rubric": {
            "requirements": 100,
            "security": 100,
            "reliability": 100,
            "usability_accessibility": 100,
            "auditability": 100,
            "rollback": 100,
        },
        "rollback_plan": "asserted rollback",
        "brain_decision": "release",
    }


@pytest.mark.xfail(strict=True, reason="Verifier propagates canonical-JSON errors instead of returning a fail-closed decision")
def test_review_requires_malformed_non_json_payload_to_fail_closed():
    envelope = {
        "instruction_id": "instruction-review-0001",
        "nonce": "nonce-review-0001",
        "signer_id": "brain-gaming-pc",
        "target_machine_id": "dev-laptop",
        "issued_at": (NOW - timedelta(seconds=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=1)).isoformat(),
        "payload": {"unsupported": object()},
        "signature": "0" * 64,
    }
    decision = verify_instruction(
        envelope,
        expected_machine_id="dev-laptop",
        secret_for_signer=lambda _: SECRET,
        replay_guard=InMemoryReplayGuard(),
        now=NOW,
    )
    assert decision.accepted is False
    assert decision.code == "malformed_instruction"


@pytest.mark.xfail(strict=True, reason="Evaluator trusts uncorrelated numeric IDs, reviewer names, scores, report text, and Brain decision")
def test_review_requires_evidence_to_be_resolved_from_authoritative_records():
    result = evaluate_capability_batch(_apparently_complete_submission(), repository_root=ROOT)
    assert result["release_candidate"] is False
    assert result["gates"]["physical_machine_evidence"] is False
    assert result["gates"]["independent_review"] is False
    assert result["gates"]["brain_release_decision"] is False


@pytest.mark.xfail(strict=True, reason="Caller can disable the required peer-response gate")
def test_review_requires_peer_evidence_for_this_batch_without_submitter_override():
    submission = _apparently_complete_submission()
    submission["requires_peer_response"] = False
    submission["physical_evidence"].pop("peer_request_id")
    result = evaluate_capability_batch(submission, repository_root=ROOT)
    assert result["gates"]["physical_machine_evidence"] is False


@pytest.mark.xfail(strict=True, reason="Generic max-five check does not enforce the exact certified five-feature manifest")
def test_review_requires_exact_batch_manifest_for_batch_02a_certificate():
    submission = _apparently_complete_submission()
    submission["feature_ids"] = ["PET-02-04"]
    result = evaluate_capability_batch(submission, repository_root=ROOT)
    assert result["gates"]["catalog_contract"] is False


@pytest.mark.xfail(strict=True, reason="Nonce table/function do not enforce append-only evidence or least-privilege execution")
def test_review_requires_database_replay_evidence_to_be_append_only_and_restricted():
    sql = (ROOT / "sql" / "migrations" / "010_pet_instruction_replay_guard.sql").read_text(encoding="utf-8").lower()
    assert "before update or delete" in sql
    assert "revoke all on pet_instruction_nonces from public" in sql
    assert "revoke execute on function consume_pet_instruction_nonce" in sql


@pytest.mark.xfail(strict=True, reason="Accepted listener receipt does not bind the verified instruction ID/decision or envelope hash")
def test_review_requires_accepted_receipt_to_bind_verified_instruction(monkeypatch):
    events = []
    message = {
        "id": 41,
        "target_id": "dev-laptop",
        "status": "delivered",
        "message_type": "brain_instruction",
        "subject": "Protected instruction",
        "priority": 80,
        "metadata": {"instruction_envelope": {"signer_id": "brain-gaming-pc"}},
    }
    monkeypatch.setattr(worker, "speaker_feed", lambda *args, **kwargs: {"messages": [message]})
    monkeypatch.setattr(
        worker,
        "verify_instruction",
        lambda *args, **kwargs: worker.InstructionDecision(True, "accepted", "PET-02-05", "instruction-0001", "dev-laptop"),
    )
    monkeypatch.setattr(worker, "submit_listener_event", lambda **kwargs: events.append(kwargs) or {"event_id": 1})
    monkeypatch.setattr(worker, "acknowledge_speaker_message", lambda *args, **kwargs: None)
    worker._consume_machine_messages("dev-laptop")
    metadata = events[0]["metadata"]
    assert metadata["instruction_decision"]["instruction_id"] == "instruction-0001"
    assert len(metadata["verified_envelope_sha256"]) == 64


@pytest.mark.xfail(strict=True, reason="Repository deployment environment has no configured Brain instruction secret")
def test_review_requires_nonempty_deployment_secret_configuration():
    env_text = (ROOT / ".env").read_text(encoding="utf-8") if (ROOT / ".env").exists() else ""
    configured = [line for line in env_text.splitlines() if line.startswith("BRAIN_INSTRUCTION_SECRET=")]
    assert configured and len(configured[0].partition("=")[2].strip()) >= 32
