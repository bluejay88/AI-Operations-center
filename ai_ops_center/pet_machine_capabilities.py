from __future__ import annotations

import ipaddress
import json
import os
import re
import uuid
from typing import Any
from urllib.parse import urlsplit

from .approvals import create_approval_request
from .brain_bus import create_speaker_message, submit_listener_event
from .config import load_machines
from .db import connect


MACHINE_PETS = {
    "brain-gaming-pc": frozenset({"executive-pet", "security-pet"}),
    "business-laptop": frozenset({"creative-pet", "security-pet"}),
    "research-laptop": frozenset({"research-pet", "security-pet"}),
    "dev-laptop": frozenset({"development-pet", "security-pet"}),
}
CAPABILITY_TYPES = frozenset({"browser_navigation", "music_playback", "device_model_chat"})
MUSIC_COMMANDS = frozenset({"play", "pause", "resume", "stop", "next", "previous"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def capability_contracts() -> dict[str, Any]:
    return {
        "capability_types": sorted(CAPABILITY_TYPES),
        "machine_pets": {machine: sorted(pets) for machine, pets in MACHINE_PETS.items()},
        "browser": {
            "allowed_schemes": sorted(_allowed_schemes()),
            "allowed_domains": sorted(_allowed_domains()),
            "public_hosts_only": True,
            "approval_required": True,
        },
        "music": {"commands": sorted(MUSIC_COMMANDS), "local_media_ids_only": True, "approval_required": True},
        "device_model_chat": {
            "device_hosted_only": True,
            "os_or_external_control": False,
            "approval_required": False,
        },
        "success_policy": "A request is never success. Only a later machine-originated receipt may report completion.",
    }


def submit_capability_request(
    *,
    machine_id: str,
    pet_id: str,
    capability_type: str,
    payload: dict[str, Any],
    requester: str,
    priority: int = 60,
    local: bool = False,
) -> dict[str, Any]:
    _validate_target(machine_id, pet_id)
    if capability_type not in CAPABILITY_TYPES:
        raise ValueError(f"unsupported capability_type {capability_type!r}")
    if not requester.strip() or len(requester) > 120:
        raise ValueError("requester must be 1-120 characters")
    normalized = _validate_payload(capability_type, payload)
    request_id = str(uuid.uuid4())
    approval_required = capability_type in {"browser_navigation", "music_playback"}
    approval_id = None
    if approval_required:
        approval_id = create_approval_request(
            title=f"Review PET {capability_type} request for {machine_id}",
            request_type="pet_machine_capability",
            requester_machine_id="brain-gaming-pc",
            requester_agent_id=pet_id,
            risk_level="high" if capability_type == "browser_navigation" else "medium",
            summary="Remote/external PET capability request is held; approval does not itself execute the action.",
            proposed_changes=json.dumps(normalized, sort_keys=True),
            metadata={"request_id": request_id, "machine_id": machine_id, "pet_id": pet_id, "capability_type": capability_type},
            local=local,
        )
    status = "pending_approval" if approval_required else "requested"
    envelope = _worker_envelope(
        request_id=request_id,
        machine_id=machine_id,
        pet_id=pet_id,
        capability_type=capability_type,
        payload=normalized,
        approval_id=approval_id,
    )
    listener = submit_listener_event(
        source_type="agent",
        source_id=pet_id,
        event_type="pet_capability_requested",
        subject=f"{capability_type} request for {machine_id}",
        body=f"Request {request_id} recorded as {status}; no success is claimed.",
        priority=priority,
        metadata=envelope,
        local=local,
    )
    speaker_id = create_speaker_message(
        target_id=machine_id,
        message_type="pet_capability_approval_hold" if approval_required else "pet_device_model_chat_request",
        subject=f"PET capability request {request_id}",
        body=(
            "DO NOT EXECUTE. Await a separately approved execution message."
            if approval_required
            else "Run only through the device-hosted model-chat executor; report completion with a machine receipt."
        ),
        priority=priority,
        metadata=envelope | {"listener_event_id": listener.get("event_id")},
        local=local,
    )
    _record_request(
        request_id=request_id,
        machine_id=machine_id,
        pet_id=pet_id,
        capability_type=capability_type,
        requester=requester,
        status=status,
        payload=normalized,
        approval_request_id=approval_id,
        listener_event_id=listener.get("event_id"),
        speaker_message_id=speaker_id,
        local=local,
    )
    return {
        "request_id": request_id,
        "machine_id": machine_id,
        "pet_id": pet_id,
        "capability_type": capability_type,
        "status": status,
        "approval_required": approval_required,
        "approval_request_id": approval_id,
        "listener_event_id": listener.get("event_id"),
        "speaker_message_id": speaker_id,
        "worker_execution_authorized": envelope["execution_authorized"],
        "machine_receipt_id": None,
        "success_claimed": False,
    }


def _worker_envelope(**values: Any) -> dict[str, Any]:
    capability_type = values["capability_type"]
    return {
        **values,
        "contract_version": "pet-machine-capability-v1",
        "executor": "device_model_chat" if capability_type == "device_model_chat" else "approval_hold",
        "execution_authorized": capability_type == "device_model_chat",
        "receipt_required_for_completion": True,
        "caller_success_assertions_ignored": True,
    }


def _validate_target(machine_id: str, pet_id: str) -> None:
    configured = {machine["id"] for machine in load_machines()}
    if machine_id not in configured or machine_id not in MACHINE_PETS:
        raise ValueError(f"unknown capability machine {machine_id!r}")
    if pet_id not in MACHINE_PETS[machine_id]:
        raise ValueError(f"PET {pet_id!r} is not assigned to machine {machine_id!r}")


def _validate_payload(capability_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if capability_type == "browser_navigation":
        if set(payload) != {"url"}:
            raise ValueError("browser_navigation payload requires only url")
        return {"url": _validate_url(str(payload["url"]))}
    if capability_type == "music_playback":
        unknown = set(payload) - {"command", "media_id"}
        if unknown:
            raise ValueError(f"unknown music fields: {', '.join(sorted(unknown))}")
        command = str(payload.get("command") or "")
        if command not in MUSIC_COMMANDS:
            raise ValueError("unsupported music command")
        media_id = payload.get("media_id")
        if command == "play" and (not isinstance(media_id, str) or not _SAFE_ID.fullmatch(media_id)):
            raise ValueError("play requires a safe local media_id")
        if media_id is not None and (not isinstance(media_id, str) or not _SAFE_ID.fullmatch(media_id)):
            raise ValueError("media_id must be a safe local identifier")
        return {"command": command, **({"media_id": media_id} if media_id is not None else {})}
    unknown = set(payload) - {"prompt", "model_id"}
    if unknown:
        raise ValueError(f"unknown model-chat fields: {', '.join(sorted(unknown))}")
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt or len(prompt) > 4000:
        raise ValueError("device model prompt must be 1-4000 characters")
    model_id = str(payload.get("model_id") or "device-default")
    if not _SAFE_ID.fullmatch(model_id):
        raise ValueError("model_id must be a safe device-local identifier")
    return {"prompt": prompt, "model_id": model_id}


def _validate_url(raw: str) -> str:
    if len(raw) > 2048:
        raise ValueError("URL exceeds 2048 characters")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in _allowed_schemes():
        raise ValueError("URL scheme is not allowed")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("URL must have a host and cannot contain credentials or fragments")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".local"):
        raise ValueError("local browser targets are not allowed")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValueError("non-public IP browser targets are not allowed")
    except ValueError as exc:
        if "non-public" in str(exc):
            raise
    allowed_domains = _allowed_domains()
    if allowed_domains and not any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains):
        raise ValueError("browser target is outside the configured domain allowlist")
    return raw


def _allowed_schemes() -> frozenset[str]:
    configured = {item.strip().lower() for item in os.getenv("PET_BROWSER_ALLOWED_SCHEMES", "https").split(",") if item.strip()}
    if not configured or not configured <= {"http", "https"}:
        raise RuntimeError("PET_BROWSER_ALLOWED_SCHEMES may contain only http and https")
    return frozenset(configured)


def _allowed_domains() -> frozenset[str]:
    return frozenset(item.strip().lower().rstrip(".") for item in os.getenv("PET_BROWSER_ALLOWED_DOMAINS", "").split(",") if item.strip())


def _record_request(**values: Any) -> None:
    local = bool(values.pop("local", False))
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pet_machine_capability_requests
                    (request_id, machine_id, pet_id, capability_type, requester, status, payload,
                     approval_request_id, listener_event_id, speaker_message_id)
                values (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    values["request_id"], values["machine_id"], values["pet_id"], values["capability_type"],
                    values["requester"], values["status"], json.dumps(values["payload"]),
                    values["approval_request_id"], values["listener_event_id"], values["speaker_message_id"],
                ),
            )
        conn.commit()
