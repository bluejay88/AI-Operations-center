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
            provider["health"] = await _model_provider_health(provider["id"])
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
        elif provider == "openai":
            result = await _dispatch_openai(prompt, purpose, options)
        elif provider == "groq":
            result = await _dispatch_groq(prompt, purpose, options)
        elif provider in {"claude", "anthropic"}:
            result = await _dispatch_claude(prompt, purpose, options)
        elif provider in {"gemini", "google"}:
            result = await _dispatch_gemini(prompt, purpose, options)
        else:
            result = {
                "status": "queued_for_manual_connector",
                "provider": provider,
                "message": "Provider credentials or SDK adapter are not wired for direct execution yet. Request recorded for supervised routing.",
            }
        _finish_integration_run(run_id, "completed", json.dumps(result, default=str), local=local)
        return {"run_id": run_id, "provider": provider, "result": result}
    except Exception as exc:
        message = _safe_error(exc)
        _finish_integration_run(run_id, "failed", message, local=local)
        return {
            "run_id": run_id,
            "provider": provider,
            "result": {
                "status": "failed",
                "provider": provider,
                "error": message,
                "message": "Provider call failed; the Brain recorded this for audit and fallback routing.",
            },
        }


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


async def _model_provider_health(provider: str) -> dict[str, Any]:
    settings = get_settings()
    configured = {
        "openai": bool(settings.openai_api_key),
        "groq": bool(settings.groq_api_key),
        "claude": bool(settings.anthropic_api_key),
        "gemini": bool(settings.google_api_key),
    }.get(provider, False)
    if not configured:
        return {"reachable": False, "configured": False, "note": "API key is not configured."}
    try:
        result = await {
            "openai": _dispatch_openai,
            "groq": _dispatch_groq,
            "claude": _dispatch_claude,
            "gemini": _dispatch_gemini,
        }[provider]("Return only: ok", "provider_healthcheck", {"max_tokens": 30})
        return {
            "reachable": result.get("status") == "completed",
            "configured": True,
            "model": result.get("model"),
            "latency_ms": result.get("latency_ms"),
        }
    except Exception as exc:
        return {"reachable": False, "configured": True, "error": _safe_error(exc)}


async def _dispatch_openai(prompt: str, purpose: str, options: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    model = options.get("model") or settings.openai_model
    started = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "input": [
                    {"role": "system", "content": f"AI Operations Center task: {purpose}. Be concise and operational."},
                    {"role": "user", "content": prompt},
                ],
                "max_output_tokens": int(options.get("max_tokens", 300)),
            },
        )
        response.raise_for_status()
        payload = response.json()
    return _provider_result("openai", model, payload, _extract_openai_text(payload), started)


async def _dispatch_groq(prompt: str, purpose: str, options: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured.")
    model = options.get("model") or settings.groq_model
    started = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"AI Operations Center task: {purpose}. Be concise and operational."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": int(options.get("max_tokens", 300)),
                "temperature": float(options.get("temperature", 0.2)),
            },
        )
        response.raise_for_status()
        payload = response.json()
    text = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    return _provider_result("groq", model, payload, text, started)


async def _dispatch_claude(prompt: str, purpose: str, options: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")
    model = options.get("model") or settings.anthropic_model
    started = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "system": f"AI Operations Center task: {purpose}. Be concise and operational.",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": int(options.get("max_tokens", 300)),
                "temperature": float(options.get("temperature", 0.2)),
            },
        )
        response.raise_for_status()
        payload = response.json()
    text = "\n".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "text").strip()
    return _provider_result("claude", model, payload, text, started)


async def _dispatch_gemini(prompt: str, purpose: str, options: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not configured.")
    model = options.get("model") or settings.google_model
    started = datetime.now(UTC)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            params={"key": settings.google_api_key},
            json={
                "systemInstruction": {"parts": [{"text": f"AI Operations Center task: {purpose}. Be concise and operational."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": int(options.get("max_tokens", 300)),
                    "temperature": float(options.get("temperature", 0.2)),
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
    candidates = payload.get("candidates") or []
    parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
    text = "\n".join(part.get("text", "") for part in parts).strip()
    return _provider_result("gemini", model, payload, text, started)


def _extract_openai_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"]).strip()
    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks).strip()


def _provider_result(provider: str, model: str, payload: dict[str, Any], text: str, started: datetime) -> dict[str, Any]:
    return {
        "status": "completed",
        "provider": provider,
        "model": model,
        "text": text,
        "latency_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 2),
        "raw_summary": {
            "id": payload.get("id"),
            "usage": payload.get("usage"),
            "finish_reason": payload.get("stop_reason") or (((payload.get("choices") or [{}])[0]).get("finish_reason")),
        },
    }


def _safe_error(exc: Exception) -> str:
    settings = get_settings()
    text = str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text[:500]
        text = f"{exc.response.status_code} {body}"
    for secret in (
        settings.openai_api_key,
        settings.groq_api_key,
        settings.anthropic_api_key,
        settings.google_api_key,
    ):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:500]


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
