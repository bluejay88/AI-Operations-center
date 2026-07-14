from __future__ import annotations

import json
from typing import Any

from .approvals import create_approval_request
from .brain_bus import create_speaker_message, submit_listener_event
from .db import connect


GOVERNED_DEVICE_OPERATIONS = {
    "open_local_browser_url",
    "local_music_play",
    "local_music_pause",
    "local_music_stop",
}

ROLE_ALLOWED_OPERATIONS = {
    "brain": {
        "publish_update",
        "run_audit",
        "run_tests",
        "git_pull",
        "git_status",
        "docker_status",
        "restart_worker",
        "sync_files",
        "model_workflow",
        "remote_browser_view",
        "remote_file_browse",
        "open_mini_dashboard",
        *GOVERNED_DEVICE_OPERATIONS,
    },
    "development": {"publish_update", "run_audit", "run_tests", "git_pull", "git_status", "build_project", "restart_worker", "open_mini_dashboard", *GOVERNED_DEVICE_OPERATIONS},
    "research": {"publish_update", "run_audit", "git_pull", "git_status", "research_task", "sync_files", "restart_worker", "open_mini_dashboard", *GOVERNED_DEVICE_OPERATIONS},
    "business": {"publish_update", "run_audit", "git_pull", "git_status", "business_task", "sync_files", "restart_worker", "open_mini_dashboard", *GOVERNED_DEVICE_OPERATIONS},
}

SENSITIVE_OPERATIONS = {"deploy", "push_git", "install_software", "change_credentials", "send_email", "delete_files", "shutdown", "restart_machine", "remote_browser_view", "remote_file_browse", *GOVERNED_DEVICE_OPERATIONS}
DESTRUCTIVE_WORDS = {"delete", "remove", "format", "wipe", "reset", "credential", "password", "secret", "send email", "payment", "browser", "files", "take over", "remote control"}


def request_remote_operation(
    machine_id: str,
    requested_by: str,
    operation_type: str,
    command_summary: str,
    priority: int = 50,
    metadata: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    metadata = metadata or {}
    decision = evaluate_remote_operation(machine_id, operation_type, command_summary, local=local)
    approval_policy = "approval_required" if decision["requires_approval"] else "preapproved"
    status = "pending_approval" if decision["requires_approval"] else "queued"

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into remote_operation_requests (
                    machine_id, requested_by, operation_type, command_summary,
                    approval_policy, status, priority, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    machine_id,
                    requested_by,
                    operation_type,
                    command_summary,
                    approval_policy,
                    status,
                    priority,
                    json.dumps({**metadata, "policy_decision": decision}),
                ),
            )
            request = dict(cur.fetchone())
        conn.commit()

    if decision["blocked"]:
        _update_operation_status(request["id"], "blocked", local=local)
        request["status"] = "blocked"
    elif decision["requires_approval"]:
        approval_id = create_approval_request(
            title=f"Remote operation approval: {operation_type} on {machine_id}",
            request_type="remote_operation",
            requester_machine_id=machine_id,
            requester_agent_id=requested_by,
            risk_level=decision["risk_level"],
            summary=command_summary,
            proposed_changes=f"Operation type: {operation_type}\nTarget machine: {machine_id}\nSummary: {command_summary}",
            metadata={"remote_operation_request_id": request["id"], **metadata, "policy_decision": decision},
            local=local,
        )
        request["approval_request_id"] = approval_id
    else:
        message_id = create_speaker_message(
            target_id=machine_id,
            message_type="remote_operation",
            subject=f"Approved operation: {operation_type}",
            body=command_summary,
            priority=priority,
            metadata={"remote_operation_request_id": request["id"], "operation_type": operation_type, **metadata},
            local=local,
        )
        request["speaker_message_id"] = message_id

    submit_listener_event(
        source_type="brain",
        source_id="remote-ops-policy",
        event_type="workload_update",
        subject=f"Remote operation {request['status']}: {operation_type}",
        body=f"{machine_id}: {command_summary}",
        priority=priority,
        metadata={"remote_operation_request_id": request["id"], "decision": decision},
        local=local,
    )
    return {"request": request, "decision": decision}


def evaluate_remote_operation(machine_id: str, operation_type: str, command_summary: str, local: bool = False) -> dict[str, Any]:
    machine_role = _machine_role(machine_id, local=local)
    allowed = ROLE_ALLOWED_OPERATIONS.get(machine_role, set()) | {"publish_update", "git_status"}
    lowered = f"{operation_type} {command_summary}".lower()
    blocked = operation_type not in allowed and operation_type not in SENSITIVE_OPERATIONS
    sensitive = operation_type in SENSITIVE_OPERATIONS or any(word in lowered for word in DESTRUCTIVE_WORDS)
    requires_approval = sensitive or operation_type not in allowed
    risk_level = "high" if sensitive else "medium" if requires_approval else "low"
    return {
        "machine_id": machine_id,
        "machine_role": machine_role,
        "operation_type": operation_type,
        "allowed_for_role": operation_type in allowed,
        "blocked": blocked,
        "requires_approval": requires_approval,
        "risk_level": risk_level,
        "allowed_operations": sorted(allowed),
    }


def remote_operation_snapshot(limit: int = 50, local: bool = False) -> list[dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from remote_operation_requests
                order by
                    case status
                        when 'queued' then 0
                        when 'pending_approval' then 1
                        when 'running' then 2
                        when 'completed' then 3
                        else 4
                    end,
                    priority desc,
                    created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def update_remote_operation_from_approval(
    operation_id: int,
    approval_decision: str,
    feedback: str,
    local: bool = False,
) -> dict[str, Any] | None:
    status_by_decision = {
        "approved": "queued",
        "rejected": "rejected",
        "needs_changes": "needs_changes",
        "deployed": "completed",
    }
    status = status_by_decision.get(approval_decision)
    if not status:
        return None

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update remote_operation_requests
                set status = %s,
                    approved_at = case when %s = 'queued' then now() else approved_at end,
                    completed_at = case when %s = 'completed' then now() else completed_at end,
                    metadata = metadata || %s::jsonb,
                    updated_at = now()
                where id = %s
                returning *
                """,
                (
                    status,
                    status,
                    status,
                    json.dumps({"approval_decision": approval_decision, "approval_feedback": feedback}),
                    operation_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def _machine_role(machine_id: str, local: bool = False) -> str:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select role from machines where id = %s", (machine_id,))
            row = cur.fetchone()
    return str((row or {}).get("role") or "unknown")


def _update_operation_status(operation_id: int, status: str, local: bool = False) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update remote_operation_requests set status = %s, updated_at = now() where id = %s",
                (status, operation_id),
            )
        conn.commit()
