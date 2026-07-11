from __future__ import annotations

from typing import Any

import httpx

from .settings import get_settings


def flowise_base_url() -> str:
    settings = get_settings()
    return (settings.flowise_url or _local_flowcheck_url() or settings.local_flowise_url).rstrip("/")


def flowise_headers() -> dict[str, str]:
    settings = get_settings()
    api_key = settings.flowise_api_key or _local_flowcheck_api_key()
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _local_flowcheck_api_key() -> str:
    try:
        from flowcheck import api_key
    except Exception:
        return ""
    return str(api_key).strip()


def _local_flowcheck_url() -> str:
    try:
        import flowcheck
    except Exception:
        return ""

    for attr in ("flowise_url", "url", "base_url"):
        value = getattr(flowcheck, attr, "")
        if value:
            return str(value).strip()
    return ""


async def healthcheck() -> dict[str, Any]:
    base_url = flowise_base_url()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(base_url, headers=flowise_headers())
        return {"base_url": base_url, "reachable": response.status_code < 500, "status_code": response.status_code}
    except httpx.HTTPError as exc:
        return {"base_url": base_url, "reachable": False, "error": str(exc)}


async def predict(chatflow_id: str, question: str, override_config: dict[str, Any] | None = None) -> dict[str, Any]:
    base_url = flowise_base_url()
    payload: dict[str, Any] = {"question": question}
    if override_config:
        payload["overrideConfig"] = override_config

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{base_url}/api/v1/prediction/{chatflow_id}",
            headers=flowise_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()
