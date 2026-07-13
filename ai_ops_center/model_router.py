from __future__ import annotations

import json
from typing import Any

from .approvals import create_approval_request
from .brain_bus import create_speaker_message, submit_listener_event
from .db import connect
from .model_workflows import run_external_model_workflow
from .tasks import create_chat_task_intake


SENSITIVE_TERMS = {
    "deploy",
    "delete",
    "password",
    "secret",
    "api key",
    "credential",
    "ssh",
    "firewall",
    "payment",
    "email campaign",
    "send email",
    "purchase",
    "install",
    "shutdown",
    "restart",
    "push",
    "merge",
}


CREATE_TABLE_SQL = """
create table if not exists model_solution_packets (
    id bigserial primary key,
    purpose text not null,
    requester text not null default 'brain-gaming-pc',
    target_id text not null default 'brain-gaming-pc',
    project_id text references projects(id) on delete set null,
    task_id bigint references tasks(id) on delete set null,
    status text not null default 'created',
    risk_level text not null default 'low',
    prompt text not null,
    provider_results jsonb not null default '[]',
    synthesized_response text not null,
    created_task_ids jsonb not null default '[]',
    approval_request_id bigint references approval_requests(id) on delete set null,
    listener_event_id bigint references listener_events(id) on delete set null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_model_solution_packets_status_time on model_solution_packets(status, created_at desc);
create index if not exists idx_model_solution_packets_project_time on model_solution_packets(project_id, created_at desc);
"""


async def submit_model_query(
    purpose: str,
    prompt: str,
    requester: str = "brain-gaming-pc",
    target_id: str = "brain-gaming-pc",
    providers: list[str] | None = None,
    project_id: str | None = None,
    task_id: int | None = None,
    priority: int = 80,
    auto_create_tasks: bool = False,
    require_approval: bool | None = None,
    options: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    options = options or {}
    governed_prompt = _governed_prompt(purpose, prompt, auto_create_tasks)
    workflow = await run_external_model_workflow(
        purpose=purpose,
        prompt=governed_prompt,
        target_id=target_id,
        providers=providers,
        task_id=task_id,
        priority=priority,
        options=options.get("provider_options") or {"max_tokens": options.get("max_tokens", 450)},
    )
    synthesis = _synthesize(workflow["results"])
    risk_level = _risk_level(f"{purpose}\n{prompt}\n{synthesis}")
    needs_approval = require_approval if require_approval is not None else risk_level in {"high", "critical"}

    created_task_ids: list[int] = []
    if auto_create_tasks and not needs_approval:
        created_task_ids = create_chat_task_intake(
            title=f"Model solution: {purpose}",
            body=_task_body(prompt, synthesis, workflow),
            requester=requester,
            priority=priority,
            local=local,
        )

    approval_request_id = None
    if needs_approval:
        approval_request_id = create_approval_request(
            title=f"Model solution requires Brain review: {purpose}",
            request_type="model_solution_review",
            requester_machine_id="brain-gaming-pc",
            requester_agent_id="model-router",
            risk_level=risk_level,
            summary=f"Model router produced a solution packet for {purpose}. Review before execution.",
            proposed_changes=_task_body(prompt, synthesis, workflow),
            metadata={"target_id": target_id, "project_id": project_id, "task_id": task_id, "requester": requester},
            local=local,
        )

    listener = submit_listener_event(
        source_type="integration",
        source_id="model-router",
        event_type="workload_update",
        subject=f"Model solution packet ready: {purpose}",
        body=f"Risk={risk_level}; approval_required={needs_approval}; tasks_created={len(created_task_ids)}.",
        priority=priority,
        metadata={
            "project_id": project_id,
            "task_id": task_id,
            "target_id": target_id,
            "risk_level": risk_level,
            "approval_request_id": approval_request_id,
            "created_task_ids": created_task_ids,
        },
        local=local,
    )
    packet_id = _record_packet(
        purpose=purpose,
        requester=requester,
        target_id=target_id,
        project_id=project_id,
        task_id=task_id,
        prompt=prompt,
        provider_results=workflow["results"],
        synthesized_response=synthesis,
        created_task_ids=created_task_ids,
        approval_request_id=approval_request_id,
        listener_event_id=listener.get("event_id"),
        risk_level=risk_level,
        status="pending_approval" if needs_approval else "queued_for_execution" if created_task_ids else "recorded",
        metadata={"workflow": workflow, "options": options},
        local=local,
    )
    _record_work_log(packet_id, purpose, project_id, task_id, synthesis, risk_level, local=local)
    if project_id:
        _record_project_note(packet_id, project_id, purpose, synthesis, local=local)

    message_id = create_speaker_message(
        target_id=target_id,
        message_type="model_solution_packet",
        subject=f"Model solution packet #{packet_id}: {purpose}",
        body=synthesis[:4000],
        priority=priority,
        metadata={
            "packet_id": packet_id,
            "approval_request_id": approval_request_id,
            "created_task_ids": created_task_ids,
            "risk_level": risk_level,
        },
        local=local,
    )
    return {
        "packet_id": packet_id,
        "status": "pending_approval" if needs_approval else "queued_for_execution" if created_task_ids else "recorded",
        "risk_level": risk_level,
        "approval_required": needs_approval,
        "approval_request_id": approval_request_id,
        "created_task_ids": created_task_ids,
        "speaker_message_id": message_id,
        "listener_event_id": listener.get("event_id"),
        "workflow": workflow,
        "synthesized_response": synthesis,
    }


def model_solution_snapshot(limit: int = 25, local: bool = False) -> list[dict[str, Any]]:
    _ensure_table(local=local)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, purpose, requester, target_id, project_id, task_id, status, risk_level,
                    created_task_ids, approval_request_id, listener_event_id, synthesized_response,
                    metadata, created_at, updated_at
                from model_solution_packets
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def _governed_prompt(purpose: str, prompt: str, auto_create_tasks: bool) -> str:
    mode = "The Brain may convert this into queued tasks after safety review." if auto_create_tasks else "The Brain will record this as a solution packet first."
    return (
        "You are advising a private AI Operations Center. Produce an implementation-ready response with:\n"
        "1. Recommended solution\n2. Concrete next actions\n3. Files/endpoints/data likely affected\n"
        "4. Tests and audits required\n5. Security risks and approval gates\n6. Worker/laptop routing recommendation.\n"
        "Do not include secrets. Do not recommend destructive action without approval.\n\n"
        f"Mode: {mode}\nPurpose: {purpose}\nRequest:\n{prompt}"
    )


def _synthesize(results: list[dict[str, Any]]) -> str:
    completed = [item for item in results if item.get("status") == "completed" and item.get("text")]
    failed = [item for item in results if item.get("status") != "completed"]
    lines = [
        "Model Router Synthesis",
        f"Completed providers: {len(completed)}",
        f"Failed or fallback providers: {len(failed)}",
        "",
    ]
    for item in completed:
        lines.append(f"[{item.get('provider')} / {item.get('model')}]")
        lines.append(str(item.get("text", "")).strip())
        lines.append("")
    for item in failed:
        lines.append(f"[{item.get('provider')} failed]")
        lines.append(str(item.get("error") or "Provider did not return a completed response."))
        lines.append("")
    return "\n".join(lines).strip()[:12000]


def _risk_level(text: str) -> str:
    lowered = text.lower()
    hits = sum(1 for term in SENSITIVE_TERMS if term in lowered)
    if any(term in lowered for term in {"delete", "credential", "api key", "password", "payment"}):
        return "critical"
    if hits >= 3:
        return "high"
    if hits:
        return "medium"
    return "low"


def _task_body(prompt: str, synthesis: str, workflow: dict[str, Any]) -> str:
    return (
        f"Original request:\n{prompt}\n\n"
        f"Model synthesis:\n{synthesis}\n\n"
        "Workflow metadata:\n"
        f"- completed providers: {workflow.get('completed')}\n"
        f"- failed providers: {workflow.get('failed')}\n"
        "Before execution: publish progress, run tests, record artifacts, and request approval for sensitive actions."
    )


def _ensure_table(local: bool = False) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()


def _record_packet(
    purpose: str,
    requester: str,
    target_id: str,
    project_id: str | None,
    task_id: int | None,
    prompt: str,
    provider_results: list[dict[str, Any]],
    synthesized_response: str,
    created_task_ids: list[int],
    approval_request_id: int | None,
    listener_event_id: int | None,
    risk_level: str,
    status: str,
    metadata: dict[str, Any],
    local: bool,
) -> int:
    _ensure_table(local=local)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into model_solution_packets (
                    purpose, requester, target_id, project_id, task_id, status, risk_level, prompt,
                    provider_results, synthesized_response, created_task_ids, approval_request_id,
                    listener_event_id, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s::jsonb)
                returning id
                """,
                (
                    purpose,
                    requester,
                    target_id,
                    project_id,
                    task_id,
                    status,
                    risk_level,
                    prompt,
                    json.dumps(provider_results),
                    synthesized_response,
                    json.dumps(created_task_ids),
                    approval_request_id,
                    listener_event_id,
                    json.dumps(metadata, default=str),
                ),
            )
            packet_id = int(cur.fetchone()["id"])
        conn.commit()
    return packet_id


def _record_work_log(packet_id: int, purpose: str, project_id: str | None, task_id: int | None, synthesis: str, risk_level: str, local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into work_logs (project_id, task_id, machine_id, agent_id, work_type, summary, status, quality_score, metadata)
                values (%s, %s, 'brain-gaming-pc', 'model-router', 'model_solution', %s, 'logged', %s, %s::jsonb)
                """,
                (
                    project_id,
                    task_id,
                    f"Model solution packet #{packet_id}: {purpose}\n\n{synthesis[:3000]}",
                    80 if risk_level in {"low", "medium"} else 60,
                    json.dumps({"packet_id": packet_id, "risk_level": risk_level}),
                ),
            )
        conn.commit()


def _record_project_note(packet_id: int, project_id: str, purpose: str, synthesis: str, local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into project_notes (project_id, note_type, title, body, source, metadata)
                values (%s, 'model_solution', %s, %s, 'model-router', %s::jsonb)
                """,
                (project_id, f"Model solution packet #{packet_id}: {purpose}", synthesis, json.dumps({"packet_id": packet_id})),
            )
        conn.commit()
