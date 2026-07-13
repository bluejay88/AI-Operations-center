from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .brain_bus import create_speaker_message, submit_listener_event
from .integrations import dispatch_to_provider


DEFAULT_PROVIDERS = ["openai", "groq", "claude", "gemini"]


async def run_external_model_workflow(
    purpose: str,
    prompt: str,
    target_id: str = "all",
    providers: list[str] | None = None,
    task_id: int | None = None,
    priority: int = 80,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_list = providers or DEFAULT_PROVIDERS
    options = options or {"max_tokens": 220}
    started_at = datetime.now(UTC).isoformat()
    results: list[dict[str, Any]] = []

    submit_listener_event(
        source_type="integration",
        source_id="external-model-workflow",
        event_type="workload_update",
        subject=f"External model workflow started: {purpose}",
        body=f"Dispatching {len(provider_list)} providers for {purpose}. Target: {target_id}.",
        priority=priority,
        metadata={"providers": provider_list, "target_id": target_id, "task_id": task_id, "started_at": started_at},
    )

    for provider in provider_list:
        result = await dispatch_to_provider(
            provider=provider,
            purpose=purpose,
            prompt=prompt,
            task_id=task_id,
            options=options,
        )
        provider_result = result.get("result", {})
        summary = {
            "provider": provider,
            "run_id": result.get("run_id"),
            "status": provider_result.get("status"),
            "model": provider_result.get("model"),
            "latency_ms": provider_result.get("latency_ms"),
            "text": (provider_result.get("text") or "")[:1200],
            "error": provider_result.get("error"),
        }
        results.append(summary)
        create_speaker_message(
            target_id=target_id,
            message_type="model_workflow_update",
            subject=f"{provider} workflow {summary['status']}: {purpose}",
            body=summary["text"] or summary.get("error") or "No provider output returned.",
            priority=priority if summary["status"] == "completed" else max(50, priority - 15),
            metadata={"provider": provider, "purpose": purpose, "task_id": task_id, "run_id": result.get("run_id"), "status": summary["status"]},
        )

    completed = [item for item in results if item.get("status") == "completed"]
    failed = [item for item in results if item.get("status") != "completed"]
    event = submit_listener_event(
        source_type="integration",
        source_id="external-model-workflow",
        event_type="workload_update",
        subject=f"External model workflow finished: {purpose}",
        body=f"External model workflow finished for {purpose}. Completed: {len(completed)}. Failed/fallback: {len(failed)}.",
        priority=priority,
        metadata={"providers": provider_list, "results": results, "target_id": target_id, "task_id": task_id, "started_at": started_at},
    )
    return {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "purpose": purpose,
        "target_id": target_id,
        "task_id": task_id,
        "completed": len(completed),
        "failed": len(failed),
        "results": results,
        "listener_event_id": event.get("event_id"),
    }
