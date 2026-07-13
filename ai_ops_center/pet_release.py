from __future__ import annotations

from typing import Any

from .approvals import create_approval_request
from .brain_bus import create_speaker_message, submit_listener_event
from .db import connect


PET_RELEASE_RUBRIC = (
    "feature_scope",
    "implementation",
    "artifacts",
    "performance",
    "tests",
    "audit",
    "rollback_plan",
)


def evaluate_pet_release_evidence(submission: dict[str, Any]) -> dict[str, Any]:
    """Evaluate evidence completeness without claiming that submitted evidence was verified."""
    feature_ids = submission.get("feature_ids") or []
    artifacts = submission.get("artifacts") or []
    performance = submission.get("performance") or {}
    tests = submission.get("tests") or {}
    audit = submission.get("audit") or {}

    checks = {
        "feature_scope": bool(feature_ids) and all(str(item).strip() for item in feature_ids),
        "implementation": bool(str(submission.get("implementation_summary") or "").strip()),
        "artifacts": bool(artifacts) and all(str(item).strip() for item in artifacts),
        "performance": _positive_int(performance.get("sample_count")) and bool(performance.get("measurements")),
        "tests": _positive_int(tests.get("total")) and _nonnegative_int(tests.get("failed")) and int(tests["failed"]) == 0 and bool(tests.get("evidence")),
        "audit": _positive_int(audit.get("total")) and _nonnegative_int(audit.get("failed")) and int(audit["failed"]) == 0 and bool(audit.get("evidence")),
        "rollback_plan": bool(str(submission.get("rollback_plan") or "").strip()),
    }
    missing = [name for name in PET_RELEASE_RUBRIC if not checks[name]]
    return {
        "checks": checks,
        "missing": missing,
        "evidence_complete": not missing,
        "verification_state": "submitted_unverified",
        "release_authorized": False,
    }


def submit_pet_release_candidate(submission: dict[str, Any], local: bool = False) -> dict[str, Any]:
    rubric = evaluate_pet_release_evidence(submission)
    machine_id = str(submission["machine_id"])
    pet_id = str(submission["pet_id"])
    metadata = {
        "machine_id": machine_id,
        "agent_id": submission["agent_id"],
        "task_id": submission.get("task_id"),
        "pet_id": pet_id,
        "feature_ids": submission.get("feature_ids") or [],
        "artifacts": submission.get("artifacts") or [],
        "performance": submission.get("performance") or {},
        "tests": submission.get("tests") or {},
        "audit": submission.get("audit") or {},
        "rollback_plan": submission.get("rollback_plan"),
        "rubric": rubric,
        "release_channel": submission.get("release_channel") or "staged",
    }
    reservation = _reserve_submission(submission, rubric, local=local)
    if not reservation["created"]:
        return {
            "submission_id": reservation["id"],
            "listener_event_id": reservation.get("listener_event_id"),
            "approval_request_id": reservation.get("approval_request_id"),
            "rubric": reservation.get("rubric") or rubric,
            "status": reservation["status"],
            "idempotent_replay": True,
        }

    event = submit_listener_event(
        source_type="machine",
        source_id=machine_id,
        event_type="pet_release_submission",
        subject=f"PET release evidence: {pet_id}",
        body=str(submission["implementation_summary"]),
        priority=int(submission.get("priority") or 85),
        metadata=metadata,
        local=local,
    )

    result: dict[str, Any] = {
        "submission_id": reservation["id"],
        "listener_event_id": event["event_id"],
        "rubric": rubric,
        "approval_request_id": None,
        "status": "needs_evidence",
    }
    if not rubric["evidence_complete"]:
        result["feedback_message_id"] = create_speaker_message(
            target_id=machine_id,
            message_type="pet_release_needs_evidence",
            subject=f"PET release evidence incomplete: {pet_id}",
            body="Submit the missing rubric evidence before Brain release review: " + ", ".join(rubric["missing"]),
            priority=max(85, int(submission.get("priority") or 85)),
            metadata={"listener_event_id": event["event_id"], "pet_id": pet_id, "missing_rubric": rubric["missing"]},
            local=local,
        )
        _finalize_submission(reservation["id"], "needs_evidence", event["event_id"], None, local=local)
        return result

    approval_id = create_approval_request(
        title=f"Review PET release candidate: {pet_id}",
        request_type="pet_release_candidate",
        requester_machine_id=machine_id,
        requester_agent_id=str(submission["agent_id"]),
        risk_level="high",
        summary=str(submission["implementation_summary"]),
        proposed_changes=(
            f"Review the submitted PET animation/features for {submission.get('release_channel') or 'staged'} release. "
            "Evidence is structurally complete but remains unverified; approval does not deploy automatically."
        ),
        metadata={"listener_event_id": event["event_id"], **metadata},
        local=local,
    )
    result.update({"approval_request_id": approval_id, "status": "pending_brain_review"})
    _finalize_submission(reservation["id"], "pending_brain_review", event["event_id"], approval_id, local=local)
    return result


def create_pet_feature_assignment(assignment: dict[str, Any], local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pet_feature_assignments (
                    assignment_key, target_machine_id, assigned_agent_id, pet_id, task_id,
                    feature_ids, acceptance_rubric, due_at, metadata
                ) values (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, nullif(%s, '')::timestamptz, %s::jsonb)
                on conflict (assignment_key) do nothing
                returning *
                """,
                (
                    assignment["assignment_key"], assignment["target_machine_id"], assignment["assigned_agent_id"],
                    assignment["pet_id"], assignment.get("task_id"), _json(assignment["feature_ids"]),
                    _json(assignment.get("acceptance_rubric") or {}), assignment.get("due_at") or "",
                    _json(assignment.get("metadata") or {}),
                ),
            )
            row = cur.fetchone()
            created = row is not None
            if not row:
                cur.execute("select * from pet_feature_assignments where assignment_key = %s", (assignment["assignment_key"],))
                row = cur.fetchone()
                if any(
                    row[key] != assignment[value]
                    for key, value in (("target_machine_id", "target_machine_id"), ("assigned_agent_id", "assigned_agent_id"), ("pet_id", "pet_id"))
                ):
                    raise ValueError("assignment_key already belongs to a different PET assignment")
        conn.commit()
    record = dict(row)
    if created:
        record["speaker_message_id"] = create_speaker_message(
            target_id=assignment["target_machine_id"], message_type="pet_feature_assignment",
            subject=f"PET feature assignment: {assignment['pet_id']}",
            body=f"Implement features {assignment['feature_ids']} and submit evidence through /pet-releases/submissions.",
            priority=int(assignment.get("priority") or 85),
            metadata={"assignment_id": record["id"], "assignment_key": assignment["assignment_key"]}, local=local,
        )
    record["idempotent_replay"] = not created
    return record


def record_pet_release_decision(
    approval_request_id: int,
    decision: str,
    actor: str,
    feedback: str,
    evidence: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any] | None:
    """Append the approval outcome to the PET ledger; never performs deployment."""
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select id from pet_release_submissions where approval_request_id = %s", (approval_request_id,))
            row = cur.fetchone()
            if not row:
                return None
            submission_id = int(row["id"])
            cur.execute(
                """
                insert into pet_release_decisions (submission_id, approval_request_id, decision, actor, feedback, evidence)
                values (%s, %s, %s, %s, %s, %s::jsonb)
                on conflict do nothing returning *
                """,
                (submission_id, approval_request_id, decision, actor, feedback, _json(evidence or {})),
            )
            decision_row = cur.fetchone()
            if decision_row:
                status = "rejected" if decision == "rejected" else "needs_evidence" if decision == "needs_changes" else decision
                cur.execute(
                    "update pet_release_submissions set status=%s, updated_at=now() where id=%s",
                    (status, submission_id),
                )
        conn.commit()
    return dict(decision_row) if decision_row else None


def ingest_pet_performance_samples(
    submission_id: int,
    machine_id: str,
    samples: list[dict[str, Any]],
    local: bool = False,
) -> dict[str, int]:
    accepted = 0
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select machine_id from pet_release_submissions where id = %s", (submission_id,))
            owner = cur.fetchone()
            if not owner or owner["machine_id"] != machine_id:
                raise ValueError(f"PET submission {submission_id} is not owned by {machine_id}")
            for sample in samples:
                cur.execute(
                    """
                    insert into pet_performance_samples (submission_id, sample_key, captured_at, metrics, tags)
                    values (%s, %s, %s::timestamptz, %s::jsonb, %s::jsonb)
                    on conflict (submission_id, sample_key) do nothing
                    """,
                    (submission_id, sample["sample_key"], sample["captured_at"], _json(sample["metrics"]), _json(sample.get("tags") or {})),
                )
                accepted += cur.rowcount
        conn.commit()
    return {"accepted": accepted, "deduplicated": len(samples) - accepted, "received": len(samples)}


def _reserve_submission(submission: dict[str, Any], rubric: dict[str, Any], local: bool) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pet_release_submissions (
                    submission_key, assignment_id, machine_id, agent_id, pet_id, task_id, feature_ids,
                    implementation_summary, artifacts, performance, tests, audit, rollback_plan, rubric, release_channel
                ) values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s, %s::jsonb, %s)
                on conflict (submission_key) do nothing returning *
                """,
                (submission["submission_key"], submission.get("assignment_id"), submission["machine_id"], submission["agent_id"],
                 submission["pet_id"], submission.get("task_id"), _json(submission["feature_ids"]), submission["implementation_summary"],
                 _json(submission.get("artifacts") or []), _json(submission.get("performance") or {}),
                 _json(submission.get("tests") or {}), _json(submission.get("audit") or {}), submission.get("rollback_plan") or "",
                 _json(rubric), submission.get("release_channel") or "staged"),
            )
            row = cur.fetchone()
            created = row is not None
            if not row:
                cur.execute("select * from pet_release_submissions where submission_key = %s", (submission["submission_key"],))
                row = cur.fetchone()
                if any(row[key] != submission[key] for key in ("machine_id", "agent_id", "pet_id")):
                    raise ValueError("submission_key already belongs to a different PET submission")
        conn.commit()
    return {**dict(row), "created": created}


def _finalize_submission(submission_id: int, status: str, listener_event_id: int, approval_request_id: int | None, local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """update pet_release_submissions set status=%s, listener_event_id=%s, approval_request_id=%s,
                    updated_at=now() where id=%s and status='processing'""",
                (status, listener_event_id, approval_request_id, submission_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"PET submission {submission_id} was not in processing state")
        conn.commit()


def _json(value: Any) -> str:
    import json
    return json.dumps(value, default=str)


def _positive_int(value: Any) -> bool:
    return _nonnegative_int(value) and int(value) > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
