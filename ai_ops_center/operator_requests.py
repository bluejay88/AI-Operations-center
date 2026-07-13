from __future__ import annotations

import json
from typing import Any

from .brain_bus import create_speaker_message
from .db import connect
from .orchestrator import create_task


DELIVERY_TASK_HINTS = {
    "dashboard": "Publish progress to the AI Operations Center dashboard.",
    "pdf": "Prepare output in a PDF-ready report structure with title, sections, tables, and source notes.",
    "docx": "Prepare output in a Word document-ready structure with headings, summary, and appendices.",
    "email": "Draft an email-ready summary for human review before sending.",
    "spreadsheet": "Prepare spreadsheet-ready rows, columns, formulas, and KPI fields.",
    "github": "Prepare GitHub-ready artifacts, branch notes, commits, or pull request text as appropriate.",
}


def create_operator_request(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    delivery_methods = payload.get("delivery_methods") or [payload.get("output_format") or "dashboard"]
    if isinstance(delivery_methods, str):
        delivery_methods = [delivery_methods]
    delivery_methods = [str(item) for item in delivery_methods if str(item).strip()]
    if not delivery_methods:
        delivery_methods = ["dashboard"]

    target_agent = payload.get("target_agent_id") or _default_agent_for_machine(payload.get("target_machine_id"))
    priority = max(1, min(100, int(payload.get("priority", 70))))
    title = str(payload["title"]).strip()
    body = str(payload["request_body"]).strip()
    output_format = str(payload.get("output_format") or delivery_methods[0] or "dashboard")

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into operator_requests (
                    title, request_body, requester, target_machine_id, target_agent_id,
                    priority, delivery_methods, output_format, due_at, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
                returning *
                """,
                (
                    title,
                    body,
                    payload.get("requester", "owner"),
                    payload.get("target_machine_id"),
                    target_agent,
                    priority,
                    json.dumps(delivery_methods),
                    output_format,
                    payload.get("due_at"),
                    json.dumps(payload.get("metadata", {})),
                ),
            )
            request = dict(cur.fetchone())
        conn.commit()

    task_ids = _route_request_to_tasks(request, delivery_methods, local=local)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update operator_requests
                set routed_task_ids = %s::jsonb,
                    updated_at = now()
                where id = %s
                returning *
                """,
                (json.dumps(task_ids), request["id"]),
            )
            request = dict(cur.fetchone())
        conn.commit()

    return {"request": request, "task_ids": task_ids}


def operator_request_snapshot(limit: int = 25, local: bool = False) -> list[dict[str, Any]]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from operator_requests
                order by
                    case status
                        when 'running' then 0
                        when 'queued' then 1
                        when 'completed' then 2
                        else 3
                    end,
                    priority desc,
                    created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def _route_request_to_tasks(request: dict[str, Any], delivery_methods: list[str], local: bool = False) -> list[int]:
    task_ids: list[int] = []
    target_agent = request.get("target_agent_id") or "project-coordinator"
    delivery_text = ", ".join(delivery_methods)
    hint_text = " ".join(DELIVERY_TASK_HINTS.get(method, f"Prepare {method} delivery.") for method in delivery_methods)
    description = (
        f"Operator request #{request['id']}: {request['request_body']}\n\n"
        f"Required delivery methods: {delivery_text}.\n"
        f"Delivery guidance: {hint_text}\n"
        "Publish workstation updates after each meaningful checkpoint. Request Brain approval before sending email, "
        "deploying externally, spending money, changing credentials, or making destructive changes."
    )
    task_ids.append(
        create_task(
            title=f"Operator request #{request['id']}: {request['title']}",
            agent_id=target_agent,
            category="operator-request",
            description=description,
            priority=int(request.get("priority", 70)),
            metadata={
                "operator_request_id": request["id"],
                "delivery_methods": delivery_methods,
                "target_machine_id": request.get("target_machine_id"),
            },
            local=local,
        )
    )
    if request.get("target_machine_id"):
        create_speaker_message(
            target_id=request["target_machine_id"],
            message_type="operator_request",
            subject=f"New operator request #{request['id']}: {request['title']}",
            body=description,
            priority=int(request.get("priority", 70)),
            metadata={"operator_request_id": request["id"], "task_ids": task_ids},
            local=local,
        )
    return task_ids


def _default_agent_for_machine(machine_id: str | None) -> str:
    if machine_id == "dev-laptop":
        return "programmer"
    if machine_id == "research-laptop":
        return "research-lead"
    if machine_id == "business-laptop":
        return "business-manager"
    return "project-coordinator"
