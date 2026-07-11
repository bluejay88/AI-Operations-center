from __future__ import annotations

from typing import Any

import httpx

from .settings import get_settings


def flowise_base_url() -> str:
    settings = get_settings()
    return (settings.flowise_url or settings.local_flowise_url).rstrip("/")


def flowise_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.flowise_api_key:
        return {}
    return {"Authorization": f"Bearer {settings.flowise_api_key}"}


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

