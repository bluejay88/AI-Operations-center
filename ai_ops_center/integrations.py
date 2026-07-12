from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from .db import connect
from .flowise import healthcheck as flowise_healthcheck
from .flowise import predict as flowise_predict
from .settings import get_settings


def integration_status() -> dict[str, Any]:
    settings = get_settings()
    providers = [
        {
            "id": "flowise",
            "label": "Flowise",
            "configured": bool(settings.flowise_url or settings.local_flowise_url),
            "capability": "visual agent flows and chain execution",
        },
        {
            "id": "n8n",
            "label": "n8n",
            "configured": bool(settings.n8n_url or settings.n8n_webhook_url),
            "capability": "automation workflows and external app handoffs",
        },
        {
            "id": "openai",
            "label": "OpenAI / ChatGPT",
            "configured": bool(settings.openai_api_key),
            "capability": "backend chat intelligence, voice, reasoning, and tool orchestration",
        },
        {
            "id": "groq",
            "label": "Groq",
            "configured": bool(settings.groq_api_key),
            "capability": "fast model responses for routing, summaries, and drafts",
        },
        {
            "id": "claude",
            "label": "Claude",
            "configured": bool(settings.anthropic_api_key),
            "capability": "long-context review, writing, and critique",
        },
        {
            "id": "gemini",
            "label": "Gemini",
            "configured": bool(settings.google_api_key),
            "capability": "research, multimodal review, and alternate model critique",
        },
    ]
    return {"generated_at": datetime.now(UTC).isoformat(), "providers": providers}


async def provider_health() -> dict[str, Any]:
    status = integration_status()
    flowise = await flowise_healthcheck()
    for provider in status["providers"]:
        if provider["id"] == "flowise":
            provider["health"] = flowise
        elif provider["id"] == "n8n":
            provider["health"] = await _n8n_health()
        else:
            provider["health"] = {"reachable": provider["configured"], "note": "API-key provider; no live call made by status check."}
    return status


async def dispatch_to_provider(
    provider: str,
    purpose: str,
    prompt: str,
    task_id: int | None = None,
    approval_request_id: int | None = None,
    options: dict[str, Any] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    options = options or {}
    run_id = _record_integration_run(provider, purpose, prompt, task_id, approval_request_id, local=local)
    result: dict[str, Any]
    try:
        if provider == "flowise":
            chatflow_id = options.get("chatflow_id")
            if not chatflow_id:
                raise ValueError("Flowise dispatch requires options.chatflow_id")
            result = await flowise_predict(chatflow_id, prompt, options.get("override_config"))
        elif provider == "n8n":
            result = await _dispatch_n8n(prompt, purpose, options)
        else:
            result = {
                "status": "queued_for_manual_connector",
                "provider": provider,
                "message": "Provider credentials or SDK adapter are not wired for direct execution yet. Request recorded for supervised routing.",
            }
        _finish_integration_run(run_id, "completed", json.dumps(result, default=str), local=local)
        return {"run_id": run_id, "provider": provider, "result": result}
    except Exception as exc:
        _finish_integration_run(run_id, "failed", str(exc), local=local)
        raise


async def _n8n_health() -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.n8n_url.rstrip("/")
    if not base_url:
        return {"reachable": False, "note": "N8N_URL is not configured."}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(base_url)
        return {"reachable": response.status_code < 500, "status_code": response.status_code}
    except httpx.HTTPError as exc:
        return {"reachable": False, "error": str(exc)}


async def _dispatch_n8n(prompt: str, purpose: str, options: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    webhook_url = options.get("webhook_url") or settings.n8n_webhook_url
    if not webhook_url:
        return {
            "status": "recorded_only",
            "message": "Set N8N_WEBHOOK_URL or options.webhook_url to send this to n8n.",
            "purpose": purpose,
        }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(webhook_url, json={"purpose": purpose, "prompt": prompt, "options": options})
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            payload = {"text": response.text}
    return {"status": "sent", "response": payload}


def _record_integration_run(
    provider: str,
    purpose: str,
    prompt: str,
    task_id: int | None,
    approval_request_id: int | None,
    local: bool,
) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into integration_runs (provider, purpose, request_body, task_id, approval_request_id)
                values (%s, %s, %s, %s, %s)
                returning id
                """,
                (provider, purpose, prompt, task_id, approval_request_id),
            )
            run_id = int(cur.fetchone()["id"])
        conn.commit()
    return run_id


def _finish_integration_run(run_id: int, status: str, response_body: str, local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update integration_runs
                set status = %s, response_body = %s, completed_at = now()
                where id = %s
                """,
                (status, response_body, run_id),
            )
        conn.commit()

