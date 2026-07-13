from __future__ import annotations

from typing import Any

from .brain_bus import create_speaker_message, submit_listener_event
from .collaboration import create_peer_request
from .operator_requests import create_operator_request
from .team_chat import post_team_chat_message, team_chat_digest, team_chat_snapshot


MACHINE_DEFAULT_AGENTS = {
    "brain-gaming-pc": "project-coordinator",
    "dev-laptop": "programmer",
    "research-laptop": "research-lead",
    "business-laptop": "business-manager",
}


def pipe_codex_request(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    title = str(payload["title"]).strip()
    body = str(payload["body"]).strip()
    requester = str(payload.get("requester") or "codex").strip()
    priority = max(1, min(100, int(payload.get("priority", 90))))
    project_id = payload.get("project_id")
    thread_key = str(payload.get("thread_key") or project_id or "codex-pipeline")
    target_machines = _clean_list(payload.get("target_machines")) or ["brain-gaming-pc"]
    delivery_methods = _clean_list(payload.get("delivery_methods")) or ["dashboard"]
    create_peer_requests = bool(payload.get("create_peer_requests", False))
    metadata = dict(payload.get("metadata") or {})
    metadata.update({"source": "codex_pipeline", "requester": requester, "target_machines": target_machines})

    team_message = post_team_chat_message(
        channel=str(payload.get("channel") or "codex"),
        thread_key=thread_key,
        actor_type="workflow",
        actor_id=requester,
        message_type="direction",
        priority=priority,
        project_id=project_id,
        subject=title,
        body=body,
        direction="Codex piped this request into the Brain for dashboard visibility, laptop assignment, and team-room follow-up.",
        confidence=90,
        metadata=metadata,
        local=local,
    )

    operator_results = []
    speaker_messages = []
    peer_requests = []
    created_task_ids: list[int] = []
    for machine_id in target_machines:
        agent_id = str(payload.get("target_agent_id") or MACHINE_DEFAULT_AGENTS.get(machine_id) or "project-coordinator")
        result = create_operator_request(
            {
                "title": title,
                "request_body": body,
                "requester": requester,
                "target_machine_id": machine_id,
                "target_agent_id": agent_id,
                "priority": priority,
                "delivery_methods": delivery_methods,
                "output_format": delivery_methods[0],
                "due_at": payload.get("due_at"),
                "metadata": {**metadata, "team_chat_message_id": team_message["id"], "project_id": project_id},
            },
            local=local,
        )
        operator_results.append(result)
        machine_task_ids = [int(task_id) for task_id in result.get("task_ids", [])]
        created_task_ids.extend(machine_task_ids)
        speaker_messages.append(
            {
                "machine_id": machine_id,
                "speaker_message_id": create_speaker_message(
                    target_id=machine_id,
                    message_type="codex_pipeline_assignment",
                    subject=f"Codex pipeline: {title}",
                    body=(
                        f"{body}\n\n"
                        "Required: read /team-chat/digest, publish progress to /team-chat/post and /listener/events, "
                        "use peer requests for help, and report completion evidence with task ids."
                    ),
                    priority=priority,
                    metadata={
                        **metadata,
                        "team_chat_message_id": team_message["id"],
                        "task_ids": machine_task_ids,
                        "all_created_task_ids": created_task_ids,
                        "delivery_methods": delivery_methods,
                        "project_id": project_id,
                        "thread_key": thread_key,
                    },
                    local=local,
                ),
            }
        )

    if create_peer_requests and len(target_machines) > 1:
        for source in target_machines:
            for target in target_machines:
                if source == target:
                    continue
                peer_requests.append(
                    create_peer_request(
                        from_machine_id=source,
                        to_machine_id=target,
                        request_type="handoff_help",
                        subject=f"Codex pipeline collaboration: {title}",
                        body=(
                            f"Coordinate on Codex pipeline thread {thread_key}. "
                            "Share research/assets/QA/status needed to complete the request without duplicating work.\n\n"
                            f"Request:\n{body}"
                        ),
                        requested_by=requester,
                        project_id=project_id,
                        priority=max(1, priority - 4),
                        metadata={**metadata, "team_chat_message_id": team_message["id"], "thread_key": thread_key},
                        local=local,
                    )
                )

    listener = submit_listener_event(
        source_type="workflow",
        source_id="codex-pipeline",
        event_type="codex_pipeline_routed",
        subject=title,
        body=f"Codex request routed to {', '.join(target_machines)} with tasks {created_task_ids}.",
        priority=priority,
        metadata={
            **metadata,
            "team_chat_message_id": team_message["id"],
            "created_task_ids": created_task_ids,
            "speaker_messages": speaker_messages,
            "peer_request_ids": [item["id"] for item in peer_requests],
        },
        local=local,
    )
    return {
        "team_chat_message": team_message,
        "operator_results": operator_results,
        "created_task_ids": created_task_ids,
        "speaker_messages": speaker_messages,
        "peer_requests": peer_requests,
        "listener_event": listener,
        "digest": team_chat_digest(limit=50, local=local),
    }


def codex_pipeline_snapshot(limit: int = 50, local: bool = False) -> dict[str, Any]:
    return {
        "pipeline_messages": team_chat_snapshot(channel="codex", limit=limit, local=local),
        "team_digest": team_chat_digest(limit=limit, local=local),
        "contract": {
            "ingest": "POST /codex/pipeline",
            "visibility": ["dashboard operator requests", "task queue", "team room", "speaker feed", "listener events"],
            "laptop_feedback": ["POST /team-chat/post", "POST /listener/events", "POST /collaboration/peer-requests", "POST /collaboration/peer-requests/{id}/respond"],
        },
    }


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
