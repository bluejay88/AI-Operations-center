from pathlib import Path

from ai_ops_center.pet_capability_certification import evaluate_capability_batch, manifest_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "ai_ops_center" / "pet_instruction_protocol.py"
REPORT = ROOT / "tests" / "test_pet_instruction_protocol.py"
FEATURE_IDS = ["PET-02-04", "PET-02-05", "PET-02-06", "PET-02-07", "PET-02-08"]


def _manifest(**overrides):
    value = {
        "batch_id": "PET-02A",
        "feature_ids": FEATURE_IDS,
        "implementation_owner": "protocol-engineer",
        "artifacts": [{"path": "ai_ops_center/pet_instruction_protocol.py", "sha256": sha256_file(ARTIFACT)}],
        "tests": {
            "passed": 19,
            "failed": 0,
            "report": {"path": "tests/test_pet_instruction_protocol.py", "sha256": sha256_file(REPORT)},
        },
        "rollback_plan": "Disable instruction intake and restore the prior worker entry point.",
        "evidence_refs": {
            "task_id": 100,
            "listener_event_id": 101,
            "peer_request_id": 102,
            "producer_machine_id": "dev-laptop",
        },
    }
    value.update(overrides)
    return value


def _authority(manifest, *, physical=True, reviews=True, release=True):
    digest = manifest_sha256(manifest)
    refs = manifest["evidence_refs"]
    result = {"manifest": manifest, "reviews": []}
    if physical:
        result.update(
            {
                "task": {
                    "id": refs["task_id"],
                    "status": "completed",
                    "claimed_by_machine": refs["producer_machine_id"],
                    "completed_at": "2026-07-13T23:00:00+00:00",
                    "metadata": {"capability_manifest_sha256": digest},
                },
                "listener": {
                    "id": refs["listener_event_id"],
                    "source_type": "machine",
                    "source_id": refs["producer_machine_id"],
                    "metadata": {"capability_manifest_sha256": digest, "task_id": refs["task_id"]},
                },
                "peer": {
                    "id": refs["peer_request_id"],
                    "task_id": refs["task_id"],
                    "status": "fulfilled",
                    "to_machine_id": refs["producer_machine_id"],
                    "responder_machine_id": refs["producer_machine_id"],
                    "responded_at": "2026-07-13T23:00:01+00:00",
                    "response_metadata": {"capability_manifest_sha256": digest},
                },
            }
        )
    if reviews:
        rubric = {
            "requirements": 95,
            "security": 95,
            "reliability": 95,
            "usability_accessibility": 90,
            "auditability": 95,
            "rollback": 90,
        }
        result["reviews"] = [
            {"manifest_sha256": digest, "reviewer_id": "quality-reviewer", "reviewer_role": "quality", "decision": "accepted", "rubric": rubric},
            {"manifest_sha256": digest, "reviewer_id": "security-reviewer", "reviewer_role": "security", "decision": "accepted", "rubric": rubric},
        ]
    if release:
        result["brain_decision"] = {
            "manifest_sha256": digest,
            "decision": "release",
            "actor": "brain-gaming-pc",
        }
    return digest, result


def _evaluate(manifest, authority):
    digest = manifest_sha256(manifest)
    return evaluate_capability_batch(
        {"manifest_sha256": digest},
        repository_root=ROOT,
        evidence_resolver=lambda requested: authority if requested == digest else {},
    )


def test_implementation_evidence_does_not_false_promote_without_physical_proof():
    manifest = _manifest()
    _, authority = _authority(manifest, physical=False, reviews=False, release=False)
    result = _evaluate(manifest, authority)
    assert result["implementation_verified"] is True
    assert result["phase"] == "awaiting_physical_evidence"
    assert result["current_ledger_state"] == "P"
    assert result["ledger_transition_authorized"] is False
    assert result["release_candidate"] is False


def test_hash_mismatch_fails_artifact_integrity_gate():
    manifest = _manifest(artifacts=[{"path": "ai_ops_center/pet_instruction_protocol.py", "sha256": "0" * 64}])
    _, authority = _authority(manifest, physical=False, reviews=False, release=False)
    result = _evaluate(manifest, authority)
    assert result["implementation_verified"] is False
    assert "artifact_integrity" in result["failed_gates"]


def test_traversal_artifact_is_rejected():
    manifest = _manifest(artifacts=[{"path": "../outside.txt", "sha256": "0" * 64}])
    _, authority = _authority(manifest, physical=False, reviews=False, release=False)
    result = _evaluate(manifest, authority)
    assert result["artifact_results"][0]["valid"] is False


def test_complete_authoritative_evidence_only_creates_candidate_not_authorization():
    manifest = _manifest()
    _, authority = _authority(manifest)
    result = _evaluate(manifest, authority)
    assert result["phase"] == "release_candidate"
    assert result["requested_transition"] == "O"
    assert result["ledger_transition_authorized"] is False


def test_owner_cannot_satisfy_independent_review():
    manifest = _manifest(implementation_owner="quality-reviewer")
    _, authority = _authority(manifest)
    result = _evaluate(manifest, authority)
    assert result["gates"]["independent_review"] is False


def test_caller_assertions_and_fabricated_ids_scores_and_decision_are_ignored():
    result = evaluate_capability_batch(
        {
            "manifest_sha256": "f" * 64,
            "feature_ids": FEATURE_IDS,
            "physical_evidence": {"task_id": 1, "listener_event_id": 2, "peer_request_id": 3},
            "reviewed_by": ["quality", "security"],
            "rubric": {dimension: 100 for dimension in ("requirements", "security", "reliability", "usability_accessibility", "auditability", "rollback")},
            "brain_decision": "release",
        },
        repository_root=ROOT,
        evidence_resolver=lambda _: {},
    )
    assert result["release_candidate"] is False
    assert result["gates"]["physical_machine_evidence"] is False
    assert result["gates"]["independent_review"] is False
    assert result["gates"]["brain_release_decision"] is False


def test_mismatched_manifest_content_is_rejected_even_when_database_row_is_returned():
    manifest = _manifest()
    digest, authority = _authority(manifest)
    authority["manifest"] = {**manifest, "rollback_plan": "tampered"}
    result = evaluate_capability_batch(
        {"manifest_sha256": digest}, repository_root=ROOT, evidence_resolver=lambda _: authority
    )
    assert result["gates"]["content_addressed_manifest"] is False
    assert result["release_candidate"] is False


def test_uncorrelated_database_rows_do_not_satisfy_physical_gate():
    manifest = _manifest()
    _, authority = _authority(manifest)
    authority["listener"]["metadata"]["task_id"] = 999
    authority["peer"]["response_metadata"]["capability_manifest_sha256"] = "0" * 64
    result = _evaluate(manifest, authority)
    assert result["gates"]["physical_machine_evidence"] is False
    assert result["release_candidate"] is False
