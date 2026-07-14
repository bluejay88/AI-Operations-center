from __future__ import annotations

import json
import re
import uuid
from typing import Any
from urllib.parse import urlsplit

from .db import connect
from .operator_requests import create_operator_request
from .pet_machine_capabilities import MACHINE_PETS, _validate_payload, dispatch_approved_request, submit_capability_request
from .team_chat import post_team_chat_message


_BROWSER = re.compile(r"^(?:please\s+)?(?:open|navigate(?:\s+to)?|browse(?:\s+to)?)\s+([^\s]+)\s*$", re.IGNORECASE)
_MUSIC_LIST = re.compile(r"^(?:please\s+)?(?:list|show|what(?:'s|\s+is))\s+(?:the\s+)?(?:available\s+)?music(?:\s+available)?\??$", re.IGNORECASE)
_MUSIC_CONTROL = re.compile(r"^(?:please\s+)?(pause|resume|stop|next|previous)(?:\s+(?:the\s+)?music)?\s*$", re.IGNORECASE)
_MUSIC_PLAY = re.compile(r"^(?:please\s+)?play(?:\s+(?:the\s+)?(?:song|track|music))?\s+(.+?)\s*$", re.IGNORECASE)
_DEVICE_MODEL = re.compile(r"^(?:please\s+)?(?:ask|query)\s+(?:the\s+)?(?:device-hosted\s+)?(?:chatgpt|device\s+model|local\s+model)\s*[:,-]?\s+(.+)$", re.IGNORECASE)
_BRAIN = re.compile(
    r"^(?:please\s+)?(?:send|submit|escalate)\s+(?:(high[- ]priority)\s+)?(?:an?\s+)?(?:enhancement\s+)?request\s+to\s+(?:the\s+)?brain\s*[:,-]?\s+(.+)$",
    re.IGNORECASE,
)
_HOSTNAME = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s]*)?$", re.IGNORECASE)
_BROWSER_ANYWHERE = re.compile(r"(?:open(?:\s+up)?(?:\s+a)?(?:\s+web)?\s+browser\s+and\s+(?:go|navigate)\s+to|navigate\s+to|go\s+to)\s+((?:https?://)?(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s,]*)?)", re.IGNORECASE)
_SONG_AFTER_THEN = re.compile(r"\b(?:and\s+)?then\s+play(?:\s+(?:the\s+)?(?:song|track))?\s+(.+?)(?:[.!?]|$)", re.IGNORECASE)


CREATE_PROPOSALS_SQL = """
create table if not exists pet_action_proposals (
    proposal_id uuid primary key,
    machine_id text not null,
    pet_id text not null,
    requester text not null,
    priority integer not null,
    action_type text not null,
    payload jsonb not null,
    summary text not null,
    status text not null default 'proposed',
    result jsonb,
    created_at timestamptz not null default now(),
    confirmed_at timestamptz
);
"""


def propose_pet_conversation_action(
    *,
    machine_id: str,
    pet_id: str,
    message: str,
    requester: str = "mini-dashboard",
    priority: int = 60,
    local: bool = False,
) -> dict[str, Any]:
    """Parse an explicit PET command into a durable, side-effect-free proposal."""
    _validate_identity(machine_id, pet_id)
    clean = " ".join(str(message or "").split())
    if not clean or len(clean) > 4000:
        raise ValueError("message must be 1-4000 characters")

    planned = _plan_action(clean)
    if planned is None:
        return _response(False, "conversation", "No explicit supported action was detected.", "not_handled", proposal_id=None)

    action_type, payload, summary = planned
    if action_type == "multi_action":
        for action in payload["actions"]:
            action["payload"] = _validate_proposal_payload(action["action_type"], action["payload"])
    elif action_type != "brain_communication":
        payload = _validate_proposal_payload(action_type, payload)
    proposal_id = str(uuid.uuid4())
    effective_priority = max(priority, int(payload.get("priority", priority)))
    _record_proposal(
        proposal_id=proposal_id, machine_id=machine_id, pet_id=pet_id, requester=requester,
        priority=effective_priority, action_type=action_type, payload=payload, summary=summary, local=local,
    )
    return _response(
        True, action_type, summary, "proposed", proposal_id=proposal_id,
    )


def confirm_pet_action_proposal(proposal_id: str, confirmed_by: str, local: bool = False) -> dict[str, Any]:
    """Idempotently submit only the immutable action stored by the proposal."""
    if not confirmed_by.strip() or len(confirmed_by) > 120:
        raise ValueError("confirmed_by must be 1-120 characters")
    proposal = _claim_proposal(proposal_id, local=local)
    if proposal.get("result"):
        return dict(proposal["result"])
    if proposal["status"] == "confirming":
        return _response(
            True, proposal["action_type"], proposal["summary"], "confirmation_in_progress",
            proposal_id=proposal_id,
        )
    if proposal["status"] != "claimed":
        raise ValueError(f"proposal {proposal_id!r} cannot be confirmed from status {proposal['status']!r}")
    try:
        if proposal["action_type"] == "brain_communication":
            result = _submit_brain_message(proposal=proposal, confirmed_by=confirmed_by, local=local)
        else:
            action_specs = proposal["payload"]["actions"] if proposal["action_type"] == "multi_action" else [
                {"action_type": proposal["action_type"], "payload": proposal["payload"]}
            ]
            requests = []
            for action in action_specs:
                request = submit_capability_request(
                    machine_id=proposal["machine_id"], pet_id=proposal["pet_id"],
                    capability_type=action["action_type"], payload=action["payload"],
                    requester=proposal["requester"], priority=int(proposal["priority"]), local=local,
                )
                if not request["approval_required"]:
                    try:
                        dispatch = dispatch_approved_request(request["request_id"], confirmed_by, local=local)
                        request = request | {"dispatch": dispatch, "status": dispatch["status"]}
                    except (RuntimeError, ValueError, PermissionError) as exc:
                        request = request | {"dispatch": {"status": "blocked", "detail": str(exc)[:240]}}
                requests.append(request)
            aggregate_status = "pending_approval" if any(item.get("approval_required") for item in requests) else str(requests[0]["status"])
            result = _response(
                True, proposal["action_type"], proposal["summary"], aggregate_status,
                proposal_id=proposal_id, capability_requests=requests,
            )
        _complete_proposal(proposal_id, result, local=local)
        return result
    except Exception:
        _release_proposal(proposal_id, local=local)
        raise


def _plan_action(message: str) -> tuple[str, dict[str, Any], str] | None:
    browser_match = _BROWSER_ANYWHERE.search(message)
    song_match = _SONG_AFTER_THEN.search(message)
    if browser_match and song_match:
        target = browser_match.group(1).rstrip(".,")
        if not target.lower().startswith(("http://", "https://")):
            target = f"https://{target}"
        song = song_match.group(1).strip().strip('"\'')
        return (
            "multi_action",
            {"actions": [
                {"action_type": "browser_navigation", "payload": {"url": target}},
                {"action_type": "music_playback", "payload": {"command": "play", "media_query": song}},
            ]},
            f"Two governed requests prepared: navigate to {target}, and ask the device's local music library to play {song}. This does not claim YouTube playback.",
        )

    if browser_match:
        target = browser_match.group(1).rstrip(".,")
        if not target.lower().startswith(("http://", "https://")):
            target = f"https://{target}"
        return "browser_navigation", {"url": target}, f"Browser navigation request prepared for {target}."

    lowered = message.lower()
    if "music" in lowered and "available" in lowered and any(term in lowered for term in {"tell me", "what", "list", "show"}):
        return "music_library", {}, "Music-library query prepared for the target device."

    if "request" in lowered and "brain" in lowered and any(term in lowered for term in {"send", "submit", "escalate", "send over"}):
        high = "high priority" in lowered or "high-priority" in lowered
        return "brain_communication", {"body": message, "priority": 90 if high else 70}, "Enhancement request prepared for Brain confirmation."

    if any(term in lowered for term in {"chatgpt", "device-hosted model", "device model", "local model"}) and any(term in lowered for term in {"ask", "query", "chat", "talk"}):
        return "device_model_chat", {"prompt": message}, "Device-hosted model request prepared."

    match = _BROWSER.fullmatch(message)
    if match:
        target = match.group(1).rstrip(".,")
        if _HOSTNAME.fullmatch(target):
            target = f"https://{target}"
        return "browser_navigation", {"url": target}, f"Browser navigation request prepared for {target}."

    if _MUSIC_LIST.fullmatch(message):
        return "music_library", {}, "Music-library query prepared for the target device."

    match = _MUSIC_CONTROL.fullmatch(message)
    if match:
        command = match.group(1).lower()
        return "music_playback", {"command": command}, f"Music {command} request prepared."

    match = _MUSIC_PLAY.fullmatch(message)
    if match:
        song = match.group(1).strip().strip('"\'')
        return "music_playback", {"command": "play", "media_query": song}, f"Playback request prepared for {song}."

    match = _DEVICE_MODEL.fullmatch(message)
    if match:
        prompt = match.group(1).strip()
        return "device_model_chat", {"prompt": prompt}, "Device-hosted model request prepared."

    match = _BRAIN.fullmatch(message)
    if match:
        requested_priority = 90 if match.group(1) else 70
        body = match.group(2).strip()
        return "brain_communication", {"body": body, "priority": requested_priority}, "Enhancement request prepared for Brain confirmation."
    return None


def _validate_proposal_payload(action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate proposal shape without applying execution-time environment policy.

    Browser domain allowlists are deployment/runtime gates. Requiring one merely
    to draft a side-effect-free proposal makes natural-language review unusable.
    Confirmation still calls submit_capability_request(), which applies the full
    public-host, scheme, domain-allowlist, approval, dispatch, and receipt gates.
    """
    if action_type != "browser_navigation":
        return _validate_payload(action_type, payload)
    if not isinstance(payload, dict) or set(payload) != {"url"}:
        raise ValueError("browser_navigation proposal requires only url")
    raw = str(payload.get("url") or "").strip()
    if not raw or len(raw) > 2048 or any(ord(character) < 32 for character in raw):
        raise ValueError("browser proposal URL must be printable and at most 2048 characters")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("browser proposal URL must use HTTP(S)")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("browser proposal URL requires a host and cannot contain credentials or fragments")
    return {"url": raw}


def _submit_brain_message(*, proposal: dict[str, Any], confirmed_by: str, local: bool) -> dict[str, Any]:
    communication_id = proposal["proposal_id"]
    body = proposal["payload"]["body"]
    priority = max(90, int(proposal["priority"])) if proposal["payload"].get("priority") == 90 else int(proposal["priority"])
    metadata = {
        "source": "pet_conversation",
        "communication_id": communication_id,
        "source_machine_id": proposal["machine_id"],
        "pet_id": proposal["pet_id"],
        "requester": proposal["requester"],
        "confirmed_by": confirmed_by,
        "execution_claimed": False,
    }
    operator = create_operator_request({
        "title": f"PET enhancement request from {proposal['pet_id']}",
        "request_body": body,
        "requester": proposal["requester"],
        "target_machine_id": "brain-gaming-pc",
        "target_agent_id": "project-coordinator",
        "priority": priority,
        "delivery_methods": ["dashboard"],
        "output_format": "dashboard",
        "metadata": metadata,
    }, local=local)
    chat = post_team_chat_message(
        channel="operations",
        thread_key=f"pet-brain:{proposal['machine_id']}",
        actor_type="agent",
        actor_id=proposal["pet_id"],
        machine_id=proposal["machine_id"],
        agent_id=proposal["pet_id"],
        message_type="direction",
        priority=priority,
        subject=f"PET enhancement request from {proposal['machine_id']}",
        body=body,
        direction="Brain review requested; no implementation is claimed.",
        metadata=metadata,
        local=local,
    )
    request_row = operator.get("request") or {}
    brain_message = {
        "communication_id": communication_id,
        "team_chat_message_id": chat.get("id"),
        "operator_request_id": request_row.get("id"),
        "task_ids": operator.get("task_ids") or [],
        "target_id": "brain-gaming-pc",
        "priority": priority,
        "status": "queued_for_brain",
        "receipt": None,
    }
    return _response(
        True, "brain_communication", proposal["summary"], "queued_for_brain",
        proposal_id=proposal["proposal_id"], brain_message=brain_message,
    )


def _response(
    handled: bool,
    action_type: str,
    summary: str,
    status: str,
    *,
    proposal_id: str | None = None,
    capability_requests: list[dict[str, Any]] | None = None,
    brain_message: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "handled": handled,
        "action_type": action_type,
        "summary": summary,
        "status": status,
        "capability_requests": capability_requests or [],
        "brain_message": brain_message,
        "success_claimed": False,
    }


def _record_proposal(**values: Any) -> None:
    local = bool(values.pop("local", False))
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_PROPOSALS_SQL)
            cur.execute(
                """insert into pet_action_proposals
                   (proposal_id,machine_id,pet_id,requester,priority,action_type,payload,summary)
                   values(%s::uuid,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (values["proposal_id"], values["machine_id"], values["pet_id"], values["requester"],
                 values["priority"], values["action_type"], json.dumps(values["payload"]), values["summary"]),
            )
        conn.commit()


def _claim_proposal(proposal_id: str, local: bool) -> dict[str, Any]:
    try:
        uuid.UUID(proposal_id)
    except ValueError as exc:
        raise ValueError("invalid proposal_id") from exc
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_PROPOSALS_SQL)
            cur.execute("update pet_action_proposals set status='confirming' where proposal_id=%s::uuid and status='proposed' returning *", (proposal_id,))
            row = cur.fetchone()
            if row:
                result = dict(row)
                result["status"] = "claimed"
            else:
                cur.execute("select * from pet_action_proposals where proposal_id=%s::uuid", (proposal_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"proposal {proposal_id!r} was not found")
                result = dict(row)
        conn.commit()
    return result


def _complete_proposal(proposal_id: str, result: dict[str, Any], local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("update pet_action_proposals set status='confirmed',result=%s::jsonb,confirmed_at=now() where proposal_id=%s::uuid", (json.dumps(result), proposal_id))
        conn.commit()


def _release_proposal(proposal_id: str, local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("update pet_action_proposals set status='proposed' where proposal_id=%s::uuid and status='confirming'", (proposal_id,))
        conn.commit()


def _validate_identity(machine_id: str, pet_id: str) -> None:
    if machine_id not in MACHINE_PETS:
        raise ValueError(f"unknown PET machine {machine_id!r}")
    if pet_id not in MACHINE_PETS[machine_id]:
        raise ValueError(f"PET {pet_id!r} is not assigned to machine {machine_id!r}")
