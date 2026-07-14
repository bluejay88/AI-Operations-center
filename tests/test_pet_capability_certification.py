from pathlib import Path

from ai_ops_center.pet_capability_certification import evaluate_capability_batch, sha256_file


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "ai_ops_center" / "pet_instruction_protocol.py"


def _submission():
    return {
        "feature_ids": ["PET-02-04", "PET-02-05", "PET-02-06", "PET-02-07", "PET-02-08"],
        "implementation_owner": "protocol-engineer",
        "artifacts": [{"path": "ai_ops_center/pet_instruction_protocol.py", "sha256": sha256_file(ARTIFACT)}],
        "tests": {"passed": 8, "failed": 0, "report": "pytest tests/test_pet_instruction_protocol.py"},
        "physical_evidence": {},
        "requires_peer_response": True,
        "reviewed_by": [],
        "rubric": {},
        "rollback_plan": "Disable instruction intake and restore the prior worker entry point.",
        "brain_decision": "hold",
    }


def test_implementation_evidence_does_not_false_promote_without_physical_proof():
    result = evaluate_capability_batch(_submission(), repository_root=ROOT)
    assert result["implementation_verified"] is True
    assert result["phase"] == "awaiting_physical_evidence"
    assert result["current_ledger_state"] == "P"
    assert result["ledger_transition_authorized"] is False
    assert result["release_candidate"] is False


def test_hash_mismatch_fails_artifact_integrity_gate():
    submission = _submission()
    submission["artifacts"][0]["sha256"] = "0" * 64
    result = evaluate_capability_batch(submission, repository_root=ROOT)
    assert result["implementation_verified"] is False
    assert "artifact_integrity" in result["failed_gates"]


def test_traversal_artifact_is_rejected():
    submission = _submission()
    submission["artifacts"] = [{"path": "../outside.txt", "sha256": "0" * 64}]
    result = evaluate_capability_batch(submission, repository_root=ROOT)
    assert result["artifact_results"][0]["valid"] is False


def test_complete_evidence_only_creates_transition_candidate_not_authorization():
    submission = _submission()
    submission["physical_evidence"] = {
        "task_id": 100,
        "listener_event_id": 101,
        "peer_request_id": 102,
        "producer_machine_id": "dev-laptop",
    }
    submission["reviewed_by"] = ["rubric-auditor", "security-monitor"]
    submission["rubric"] = {
        "requirements": 95,
        "security": 95,
        "reliability": 95,
        "usability_accessibility": 90,
        "auditability": 95,
        "rollback": 90,
    }
    submission["brain_decision"] = "release"
    result = evaluate_capability_batch(submission, repository_root=ROOT)
    assert result["phase"] == "release_candidate"
    assert result["requested_transition"] == "O"
    assert result["ledger_transition_authorized"] is False


def test_owner_cannot_satisfy_independent_review():
    submission = _submission()
    submission["implementation_owner"] = "rubric-auditor"
    submission["reviewed_by"] = ["rubric-auditor", "security-monitor"]
    result = evaluate_capability_batch(submission, repository_root=ROOT)
    assert result["gates"]["independent_review"] is False
