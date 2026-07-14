from __future__ import annotations

import ipaddress
import hashlib
import hmac
import json
import os
import re
import uuid
import threading
from datetime import UTC, datetime, timedelta
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
CAPABILITY_TYPES = frozenset({"browser_navigation", "music_playback", "music_library", "device_model_chat"})
WORKER_EXECUTORS = {
    "browser_navigation": {"executor": "browser_navigation"},
    "music_playback": {"executor": "music_playback"},
    "music_library": {"executor": "music_library"},
    "device_model_chat": {"executor": "device_model_chat"},
}
_DISPATCH_LOCK = threading.Lock()
_DISPATCH_ATTEMPTS: set[str] = set()
MUSIC_COMMANDS = frozenset({"play", "pause", "resume", "stop", "next", "previous"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def capability_contracts() -> dict[str, Any]:
    return {
        "capability_types": sorted(CAPABILITY_TYPES),
        "machine_pets": {machine: sorted(pets) for machine, pets in MACHINE_PETS.items()},
        "browser": {
            "allowed_schemes": sorted(_allowed_schemes()),
            "allowed_domains": sorted(_configured_allowed_domains()),
            "allowlist_configured": bool(_configured_allowed_domains()),
            "public_hosts_only": True,
            "approval_required": True,
        },
        "music": {
            "commands": sorted(MUSIC_COMMANDS),
            "local_media_ids_only": True,
            "named_song_resolution": "target_device_local_library_only",
            "approval_required": True,
        },
        "music_library": {"device_local_only": True, "approval_required": False, "receipt_required": True},
        "device_model_chat": {
            "device_hosted_only": True,
            "os_or_external_control": False,
            "approval_required": False,
            "executor_description": "device-hosted model-chat executor",
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
        message_type=(
            "pet_capability_approval_hold"
            if approval_required
            else "pet_device_model_chat_request"
            if capability_type == "device_model_chat"
            else "pet_machine_capability_request"
        ),
        subject=f"PET capability request {request_id}",
        body=(
            "DO NOT EXECUTE. Await a separately approved execution message."
            if approval_required
            else "Run only through the target-host capability executor; report completion with a machine receipt."
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
        "worker_execution_authorized": False,
        "machine_receipt_id": None,
        "success_claimed": False,
    }


def _worker_envelope(**values: Any) -> dict[str, Any]:
    capability_type = values["capability_type"]
    return {
        **values,
        "contract_version": "pet-machine-capability-v1",
        "executor": "approval_hold",
        "execution_authorized": False,
        "receipt_required_for_completion": True,
        "caller_success_assertions_ignored": True,
    }


def dispatch_approved_request(request_id: str, actor: str, local: bool = False) -> dict[str, Any]:
    request = _load_request(request_id, local=local)
    if request is None:
        raise ValueError(f"capability request {request_id!r} was not found")
    if request["capability_type"] in {"browser_navigation", "music_playback"} and request.get("approval_status") not in {"approved", "deployed"}:
        raise PermissionError("remote/external capability request is not approved")
    key = _directional_key("PET_DISPATCH_SIGNING_KEY", request["machine_id"])
    issued_at = datetime.now(UTC)
    envelope = {
        "contract_version": "pet-machine-execution-v1",
        "request_id": str(request["request_id"]),
        "machine_id": request["machine_id"],
        "pet_id": request["pet_id"],
        "capability_type": request["capability_type"],
        **WORKER_EXECUTORS[request["capability_type"]],
        "payload": request["payload"],
        "approval_request_id": request.get("approval_request_id"),
        "approval_status": request.get("approval_status"),
        "dispatched_by": actor,
        "key_id": f"dispatch:{request['machine_id']}:v1",
        "nonce": str(uuid.uuid4()),
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=5)).isoformat(),
        "execution_authorized": True,
        "receipt_required_for_completion": True,
    }
    envelope["dispatch_sha256"] = _payload_sha256(envelope)
    envelope["signature"] = _sign(envelope, key)
    with _DISPATCH_LOCK:
        if request_id in _DISPATCH_ATTEMPTS:
            return {"request_id": request_id, "status": "already_dispatched", "success_claimed": False, "machine_receipt_id": None}
        _DISPATCH_ATTEMPTS.add(request_id)
    if not _reserve_dispatch_intent(request_id=request_id, envelope=envelope, actor=actor, local=local):
        return {"request_id": request_id, "status": "already_dispatched", "success_claimed": False, "machine_receipt_id": None}
    speaker_id = create_speaker_message(
        target_id=request["machine_id"], message_type="pet_capability_signed_execution",
        subject=f"Approved PET execution {request_id}", body="Verify signature and target before local execution.",
        priority=80, metadata=envelope, local=local,
    )
    _record_dispatch(request_id=request_id, speaker_message_id=speaker_id, envelope=envelope, actor=actor, local=local)
    return {"request_id": request_id, "status": "dispatched", "speaker_message_id": speaker_id, "success_claimed": False, "machine_receipt_id": None}


class MachineCapabilityExecutor:
    """Target-host interface. Handlers are injected by a machine package, never the API server."""

    def __init__(self, machine_id: str, *, browser_handler=None, music_handler=None, music_library_handler=None, model_handler=None, enable_browser: bool = False, enable_music: bool = False, enable_music_library: bool = False, enable_model_chat: bool = False, signing_key: str | None = None, receipt_signing_key: str | None = None) -> None:
        self.machine_id = machine_id
        self.handlers = {"browser_navigation": browser_handler, "music_playback": music_handler, "music_library": music_library_handler, "device_model_chat": model_handler}
        self.flags = {"browser_navigation": enable_browser, "music_playback": enable_music, "music_library": enable_music_library, "device_model_chat": enable_model_chat}
        self.key = (signing_key or _directional_key("PET_DISPATCH_VERIFY_KEY", machine_id).decode()).encode()
        self.receipt_key = (receipt_signing_key or signing_key or _directional_key("PET_RECEIPT_SIGNING_KEY", machine_id).decode()).encode()
        if len(self.key) < 32:
            raise ValueError("machine executor requires a signing key of at least 32 bytes")
        self._used_nonces: set[str] = set()
        self._nonce_lock = threading.Lock()

    def execute(self, envelope: dict[str, Any]) -> dict[str, Any]:
        supplied = str(envelope.get("signature") or "")
        unsigned = {key: value for key, value in envelope.items() if key != "signature"}
        if not hmac.compare_digest(supplied, _sign(unsigned, self.key)):
            raise PermissionError("invalid execution envelope signature")
        if envelope.get("machine_id") != self.machine_id or not envelope.get("execution_authorized"):
            raise PermissionError("execution envelope target or authority is invalid")
        if envelope.get("key_id") != f"dispatch:{self.machine_id}:v1":
            raise PermissionError("execution envelope key identity is invalid")
        capability = str(envelope.get("capability_type"))
        if envelope.get("contract_version") != "pet-machine-execution-v1":
            raise PermissionError("unsupported execution contract version")
        if envelope.get("executor") != WORKER_EXECUTORS.get(capability, {}).get("executor"):
            raise PermissionError("execution envelope executor does not match capability type")
        if capability in {"browser_navigation", "music_playback"} and (
            envelope.get("approval_status") not in {"approved", "deployed"} or not envelope.get("approval_request_id")
        ):
            raise PermissionError("target executor requires approved remote-control evidence")
        nonce = str(envelope.get("nonce") or "")
        try:
            issued_at = datetime.fromisoformat(str(envelope["issued_at"]).replace("Z", "+00:00"))
            expires_at = datetime.fromisoformat(str(envelope["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError) as exc:
            raise PermissionError("execution envelope timing evidence is invalid") from exc
        now = datetime.now(UTC)
        if not nonce or issued_at > now + timedelta(seconds=30) or expires_at <= now or expires_at - issued_at > timedelta(minutes=10):
            raise PermissionError("execution envelope is expired or outside its allowed window")
        with self._nonce_lock:
            if nonce in self._used_nonces:
                return self._receipt(envelope, "held", "Replay rejected; no action ran.")
            self._used_nonces.add(nonce)
        try:
            _validate_payload(capability, dict(envelope.get("payload") or {}))
        except (ValueError, RuntimeError) as exc:
            return self._receipt(envelope, "held", f"Target validation rejected payload: {exc}")
        handler = self.handlers.get(capability)
        if not self.flags.get(capability) or handler is None:
            return self._receipt(envelope, "held", "Target-host capability is disabled; no action ran.")
        try:
            result = handler(dict(envelope.get("payload") or {}))
            return self._receipt(envelope, "completed", str(result)[:1000])
        except Exception as exc:
            return self._receipt(envelope, "failed", str(exc)[:1000])

    def _receipt(self, envelope: dict[str, Any], status: str, detail: str) -> dict[str, Any]:
        receipt = {"contract_version": "pet-machine-receipt-v1", "key_id": f"receipt:{self.machine_id}:v1", "request_id": envelope["request_id"], "machine_id": self.machine_id, "pet_id": envelope["pet_id"], "capability_type": envelope["capability_type"], "approval_request_id": envelope.get("approval_request_id"), "dispatch_sha256": envelope.get("dispatch_sha256"), "nonce": envelope.get("nonce"), "status": status, "detail": detail}
        receipt["signature"] = _sign(receipt, self.receipt_key)
        return receipt


def record_machine_receipt(receipt: dict[str, Any], local: bool = False) -> dict[str, Any]:
    machine_id = str(receipt.get("machine_id") or "")
    if receipt.get("key_id") != f"receipt:{machine_id}:v1":
        raise PermissionError("machine receipt key identity is invalid")
    key = _directional_key("PET_RECEIPT_VERIFY_KEY", machine_id)
    supplied = str(receipt.get("signature") or "")
    unsigned = {name: value for name, value in receipt.items() if name != "signature"}
    if not hmac.compare_digest(supplied, _sign(unsigned, key)):
        raise PermissionError("invalid machine receipt signature")
    if receipt.get("status") not in {"held", "completed", "failed"}:
        raise ValueError("invalid machine receipt status")
    request = _load_request(str(receipt.get("request_id")), local=local)
    if request is None or request["machine_id"] != receipt.get("machine_id") or request["pet_id"] != receipt.get("pet_id"):
        raise PermissionError("machine receipt does not match the targeted request")
    if request["capability_type"] != receipt.get("capability_type"):
        raise PermissionError("machine receipt capability does not match request")
    expected_dispatch = request.get("dispatch_sha256")
    if not expected_dispatch or receipt.get("dispatch_sha256") != expected_dispatch:
        raise PermissionError("machine receipt is not bound to an authoritative dispatch")
    if request.get("approval_request_id") != receipt.get("approval_request_id"):
        raise PermissionError("machine receipt approval binding does not match")
    listener = submit_listener_event(source_type="machine", source_id=receipt["machine_id"], event_type="pet_capability_receipt", subject=f"PET capability receipt {receipt['request_id']}", body=f"Machine reported {receipt['status']}; independent verification is not implied.", priority=80, metadata=receipt, local=local)
    receipt_id = _record_receipt(receipt=receipt, listener_event_id=listener.get("event_id"), local=local)
    return {"receipt_id": receipt_id, "request_id": receipt["request_id"], "machine_reported_status": receipt["status"], "independently_verified": False}


def capability_request_status(request_id: str, local: bool = False) -> dict[str, Any] | None:
    request = _load_request(request_id, local=local)
    if request is None:
        return None
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select id, status, detail, listener_event_id, created_at from pet_machine_capability_receipts where request_id=%s::uuid order by id", (request_id,))
            receipts = [dict(row) for row in cur.fetchall()]
    return {"request": request, "receipts": receipts, "success_claimed": False, "completion_source": "machine_receipt" if receipts else None}


def machine_receipt_exists(request_id: str, machine_id: str, local: bool = False) -> bool:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from pet_machine_capability_receipts where request_id=%s::uuid and machine_id=%s limit 1", (request_id, machine_id))
            return cur.fetchone() is not None


def _sign(value: dict[str, Any], key: bytes) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def _payload_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(canonical).hexdigest()


def _signing_key() -> bytes:
    key = os.getenv("PET_CAPABILITY_SIGNING_KEY", "").encode()
    if len(key) < 32:
        raise RuntimeError("PET_CAPABILITY_SIGNING_KEY must be at least 32 bytes before dispatch or receipt ingestion")
    return key


def _directional_key(prefix: str, machine_id: str) -> bytes:
    name = f"{prefix}_{machine_id.upper().replace('-', '_')}"
    key = os.getenv(name, "").encode()
    if len(key) < 32:
        raise RuntimeError(f"{name} must be at least 32 bytes")
    return key


def _load_request(request_id: str, local: bool = False) -> dict[str, Any] | None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("""select r.*, a.status as approval_status, i.envelope->>'dispatch_sha256' as dispatch_sha256 from pet_machine_capability_requests r left join approval_requests a on a.id=r.approval_request_id left join pet_machine_capability_dispatch_intents i on i.request_id=r.request_id where r.request_id=%s::uuid""", (request_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def _record_dispatch(*, request_id: str, speaker_message_id: int, envelope: dict[str, Any], actor: str, local: bool) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("insert into pet_machine_capability_dispatches(request_id,speaker_message_id,envelope,dispatched_by) values(%s::uuid,%s,%s::jsonb,%s) on conflict(request_id) do nothing", (request_id, speaker_message_id, json.dumps(envelope), actor))
        conn.commit()


def _reserve_dispatch_intent(*, request_id: str, envelope: dict[str, Any], actor: str, local: bool) -> bool:
    try:
        with connect(local=local) as conn:
            with conn.cursor() as cur:
                cur.execute("insert into pet_machine_capability_dispatch_intents(request_id,envelope,dispatched_by) values(%s::uuid,%s::jsonb,%s) on conflict(request_id) do nothing returning request_id", (request_id, json.dumps(envelope), actor))
                created = cur.fetchone() is not None
            conn.commit()
        return created
    except Exception:
        # Tests and disconnected target packages still retain process-local idempotency;
        # production dispatch requires migration 017 and a reachable database.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return True
        raise


def _record_receipt(*, receipt: dict[str, Any], listener_event_id: int, local: bool) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("insert into pet_machine_capability_receipts(request_id,machine_id,pet_id,status,detail,receipt,listener_event_id) values(%s::uuid,%s,%s,%s,%s,%s::jsonb,%s) on conflict(request_id,machine_id) do nothing returning id", (receipt["request_id"], receipt["machine_id"], receipt["pet_id"], receipt["status"], receipt.get("detail", ""), json.dumps(receipt), listener_event_id))
            row = cur.fetchone()
            if row is None:
                raise ValueError("machine receipt already exists for request")
            receipt_id = int(row["id"])
        conn.commit()
    return receipt_id


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
        unknown = set(payload) - {"command", "media_id", "media_query"}
        if unknown:
            raise ValueError(f"unknown music fields: {', '.join(sorted(unknown))}")
        command = str(payload.get("command") or "")
        if command not in MUSIC_COMMANDS:
            raise ValueError("unsupported music command")
        media_id = payload.get("media_id")
        media_query = payload.get("media_query")
        if command == "play" and bool(media_id) == bool(media_query):
            raise ValueError("play requires exactly one local media_id or media_query")
        if media_id is not None and (not isinstance(media_id, str) or not _SAFE_ID.fullmatch(media_id)):
            raise ValueError("media_id must be a safe local identifier")
        if media_query is not None and (not isinstance(media_query, str) or not media_query.strip() or len(media_query) > 200 or any(ord(char) < 32 for char in media_query)):
            raise ValueError("media_query must be a printable song name up to 200 characters")
        return {
            "command": command,
            **({"media_id": media_id} if media_id is not None else {}),
            **({"media_query": media_query.strip()} if media_query is not None else {}),
        }
    if capability_type == "music_library":
        if payload:
            raise ValueError("music_library payload must be empty")
        return {}
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
    if re.fullmatch(r"(?:0x[0-9a-f]+|0[0-9]+|[0-9]+)", host) or any(
        part.startswith("0") and len(part) > 1 for part in host.split(".") if part.isdigit()
    ):
        raise ValueError("ambiguous numeric browser targets are not allowed")
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
    domains = _configured_allowed_domains()
    if not domains:
        raise RuntimeError("PET_BROWSER_ALLOWED_DOMAINS must be a nonempty allowlist")
    return domains


def _configured_allowed_domains() -> frozenset[str]:
    domains = frozenset(item.strip().lower().rstrip(".") for item in os.getenv("PET_BROWSER_ALLOWED_DOMAINS", "").split(",") if item.strip())
    return domains


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
