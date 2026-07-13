from ai_ops_center import pet_release


def _submission() -> dict:
    return {
        "submission_key": "nova-42-attempt-1",
        "assignment_id": None,
        "machine_id": "dev-laptop",
        "agent_id": "pet-animation-agent",
        "pet_id": "nova",
        "task_id": 42,
        "feature_ids": ["PET-ANIM-001"],
        "implementation_summary": "Added a reduced-motion-safe workload animation.",
        "artifacts": ["artifacts/nova-workload.webm"],
        "performance": {"sample_count": 20, "measurements": {"p95_frame_ms": 12.4}},
        "tests": {"total": 8, "failed": 0, "evidence": "reports/nova-tests.json"},
        "audit": {"total": 12, "failed": 0, "evidence": "reports/nova-audit.json"},
        "rollback_plan": "Restore the previous PET animation asset and manifest entry.",
        "release_channel": "canary",
        "priority": 88,
    }


def test_evidence_gate_requires_real_counts_and_references():
    submission = _submission()
    submission["tests"] = {"total": 0, "failed": 0, "evidence": ""}

    rubric = pet_release.evaluate_pet_release_evidence(submission)

    assert rubric["evidence_complete"] is False
    assert "tests" in rubric["missing"]
    assert rubric["verification_state"] == "submitted_unverified"
    assert rubric["release_authorized"] is False


def test_incomplete_submission_returns_feedback_without_approval(monkeypatch):
    submission = _submission()
    submission["audit"]["failed"] = 1
    monkeypatch.setattr(pet_release, "submit_listener_event", lambda **kwargs: {"event_id": 71, "actions": []})
    monkeypatch.setattr(pet_release, "_reserve_submission", lambda *args, **kwargs: {"id": 11, "created": True})
    monkeypatch.setattr(pet_release, "_finalize_submission", lambda *args, **kwargs: None)
    messages = []
    monkeypatch.setattr(pet_release, "create_speaker_message", lambda **kwargs: messages.append(kwargs) or 91)
    monkeypatch.setattr(pet_release, "create_approval_request", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not approve")))

    result = pet_release.submit_pet_release_candidate(submission)

    assert result["status"] == "needs_evidence"
    assert result["approval_request_id"] is None
    assert messages[0]["target_id"] == "dev-laptop"
    assert "audit" in messages[0]["metadata"]["missing_rubric"]


def test_complete_submission_creates_high_risk_review_not_release(monkeypatch):
    submission = _submission()
    captured = {}
    monkeypatch.setattr(pet_release, "submit_listener_event", lambda **kwargs: {"event_id": 72, "actions": []})
    monkeypatch.setattr(pet_release, "_reserve_submission", lambda *args, **kwargs: {"id": 12, "created": True})
    monkeypatch.setattr(pet_release, "_finalize_submission", lambda *args, **kwargs: None)
    monkeypatch.setattr(pet_release, "create_speaker_message", lambda **kwargs: 0)

    def create_approval(**kwargs):
        captured.update(kwargs)
        return 101

    monkeypatch.setattr(pet_release, "create_approval_request", create_approval)

    result = pet_release.submit_pet_release_candidate(submission)

    assert result["status"] == "pending_brain_review"
    assert result["approval_request_id"] == 101
    assert result["rubric"]["release_authorized"] is False
    assert captured["risk_level"] == "high"
    assert captured["metadata"]["rubric"]["verification_state"] == "submitted_unverified"
    assert "does not deploy automatically" in captured["proposed_changes"]


def test_idempotent_replay_does_not_repeat_brain_side_effects(monkeypatch):
    submission = _submission()
    monkeypatch.setattr(
        pet_release,
        "_reserve_submission",
        lambda *args, **kwargs: {
            "id": 12,
            "created": False,
            "status": "pending_brain_review",
            "listener_event_id": 72,
            "approval_request_id": 101,
            "rubric": pet_release.evaluate_pet_release_evidence(submission),
        },
    )
    monkeypatch.setattr(pet_release, "submit_listener_event", lambda **kwargs: (_ for _ in ()).throw(AssertionError("duplicate listener")))
    monkeypatch.setattr(pet_release, "create_approval_request", lambda **kwargs: (_ for _ in ()).throw(AssertionError("duplicate approval")))

    result = pet_release.submit_pet_release_candidate(submission)

    assert result["idempotent_replay"] is True
    assert result["approval_request_id"] == 101
