from __future__ import annotations

from typing import Any

from .approvals import approval_snapshot, review_approval_request
from .brain_bus import create_speaker_message, submit_listener_event
from .remote_ops import update_remote_operation_from_approval


HIGH_IMPACT_TERMS = {
    "change_credentials",
    "credential",
    "password",
    "secret",
    "delete",
    "remove",
    "deploy",
    "send_email",
    "bank",
    "payment",
    "legal",
    "tax",
    "contract",
    "public",
    "publish",
}

REQUIRED_EVIDENCE = [
    "exact action requested",
    "target device or project",
    "rollback or recovery plan",
    "test evidence or validation plan",
    "security impact",
]


def process_approval_queue(limit: int = 20, actor: str = "brain-approval-processor", local: bool = False) -> dict[str, Any]:
    processed: list[dict[str, Any]] = []
    approvals = approval_snapshot(limit=limit, local=local)
    for approval in approvals:
        if approval.get("status") != "pending":
            continue
        decision, feedback = _decision_for(approval)
        if decision == "hold":
            _notify_brain_hold(approval, feedback, local=local)
            processed.append({"approval_request_id": approval["id"], "decision": "hold", "feedback": feedback})
            continue

        reviewed = review_approval_request(
            int(approval["id"]),
            decision,
            feedback,
            actor=actor,
            metadata={"processed_by": "approval_processor", "reason": decision},
            local=local,
        )
        _route_reviewed_approval(reviewed, decision, feedback, local=local)
        processed.append({"approval_request_id": approval["id"], "decision": decision, "feedback": feedback})

    event = submit_listener_event(
        source_type="brain",
        source_id="approval-processor",
        event_type="workload_update",
        subject="Approval queue processed",
        body=f"Processed {len(processed)} approval records. Decisions: {processed}",
        priority=82,
        metadata={"processed": processed},
        local=local,
    )
    return {"processed": processed, "listener_event_id": event.get("event_id")}


def _decision_for(approval: dict[str, Any]) -> tuple[str, str]:
    text = " ".join(
        str(approval.get(key) or "")
        for key in ["title", "request_type", "risk_level", "summary", "proposed_changes"]
    ).lower()
    missing = [item for item in REQUIRED_EVIDENCE if item not in text]
    high_impact = approval.get("risk_level") in {"high", "critical"} or any(term in text for term in HIGH_IMPACT_TERMS)

    if high_impact:
        return (
            "needs_changes",
            "Brain reviewed this as high-impact. Cycle back with exact evidence before approval: exact key/fingerprint or artifact, target device/project, validation output, rollback plan, security impact, and explicit Jayla approval when credentials, deployment, money, legal, public sending, or destructive actions are involved.",
        )

    if missing:
        return (
            "needs_changes",
            "Brain needs more evidence before approval: include " + ", ".join(missing) + ".",
        )

    if approval.get("risk_level") == "low":
        return (
            "approved",
            "Approved as low-risk, reversible, and within current automation policy. Execute through the worker/speaker path and report completion evidence back to Brain.",
        )

    return (
        "needs_changes",
        "Medium-risk request reviewed. Add test output, artifact path, rollback plan, security notes, and exact execution target before approval.",
    )


def _route_reviewed_approval(reviewed: dict[str, Any], decision: str, feedback: str, local: bool = False) -> None:
    metadata = dict(reviewed.get("metadata") or {})
    remote_operation_id = metadata.get("remote_operation_request_id")
    if remote_operation_id:
        update_remote_operation_from_approval(int(remote_operation_id), decision, feedback, local=local)

    target = reviewed.get("requester_machine_id") or "brain-gaming-pc"
    create_speaker_message(
        target_id=target,
        message_type=f"approval_{decision}",
        subject=f"Approval {decision}: {reviewed.get('title')}",
        body=feedback,
        priority=92 if decision in {"approved", "needs_changes"} else 70,
        metadata={"approval_request_id": reviewed.get("id"), "decision": decision},
        local=local,
    )


def _notify_brain_hold(approval: dict[str, Any], feedback: str, local: bool = False) -> None:
    create_speaker_message(
        target_id="brain-gaming-pc",
        message_type="approval_human_review_needed",
        subject=f"Human approval needed: {approval.get('title')}",
        body=feedback,
        priority=96,
        metadata={"approval_request_id": approval.get("id")},
        local=local,
    )
