from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol


INSTRUCTION_FEATURE_IDS = (
    "PET-02-04",
    "PET-02-05",
    "PET-02-06",
    "PET-02-07",
    "PET-02-08",
)
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_SIGNATURE_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ReplayGuard(Protocol):
    def consume(
        self,
        signer_id: str,
        nonce: str,
        instruction_id: str,
        target_machine_id: str,
        expires_at: datetime,
        now: datetime,
    ) -> bool:
        """Atomically return True once for a nonce and False for every replay."""


class InMemoryReplayGuard:
    """Thread-safe process-local replay protection for workers and deterministic tests.

    A shared database-backed implementation is required before multi-process certification.
    """

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    def consume(
        self,
        signer_id: str,
        nonce: str,
        instruction_id: str,
        target_machine_id: str,
        expires_at: datetime,
        now: datetime,
    ) -> bool:
        with self._lock:
            self._seen = {key: expiry for key, expiry in self._seen.items() if expiry > now}
            key = (signer_id, nonce)
            if key in self._seen:
                return False
            self._seen[key] = expires_at
            return True


class PostgresReplayGuard:
    """Database-backed atomic replay protection shared by all worker processes."""

    def __init__(self, *, local: bool = False) -> None:
        self.local = local

    def consume(
        self,
        signer_id: str,
        nonce: str,
        instruction_id: str,
        target_machine_id: str,
        expires_at: datetime,
        now: datetime,
    ) -> bool:
        from .db import connect

        with connect(local=self.local) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select consume_pet_instruction_nonce(%s, %s, %s, %s, %s)",
                    (signer_id, nonce, instruction_id, target_machine_id, expires_at),
                )
                accepted = bool(cur.fetchone()["consume_pet_instruction_nonce"])
            conn.commit()
        return accepted


@dataclass(frozen=True)
class InstructionDecision:
    accepted: bool
    code: str
    feature_id: str
    instruction_id: str | None = None
    target_machine_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "code": self.code,
            "feature_id": self.feature_id,
            "instruction_id": self.instruction_id,
            "target_machine_id": self.target_machine_id,
        }


def sign_instruction(unsigned: Mapping[str, Any], secret: bytes) -> dict[str, Any]:
    """Return a copy with an HMAC-SHA256 signature over canonical JSON."""
    _validate_secret(secret)
    envelope = dict(unsigned)
    envelope.pop("signature", None)
    envelope["signature"] = hmac.new(secret, _canonical(envelope), hashlib.sha256).hexdigest()
    return envelope


def verify_instruction(
    envelope: Mapping[str, Any],
    *,
    expected_machine_id: str,
    secret_for_signer: Callable[[str], bytes | None],
    replay_guard: ReplayGuard,
    now: datetime | None = None,
    maximum_ttl: timedelta = timedelta(hours=24),
    future_skew: timedelta = timedelta(minutes=2),
) -> InstructionDecision:
    """Fail closed on malformed, unsigned, expired, mistargeted, or replayed instructions."""
    current = _utc(now or datetime.now(timezone.utc))
    parsed = _parse(envelope)
    if isinstance(parsed, InstructionDecision):
        return parsed

    instruction_id, nonce, signer_id, target, issued_at, expires_at, signature = parsed
    secret = secret_for_signer(signer_id)
    if secret is None or len(secret) < 32 or not _SIGNATURE_PATTERN.fullmatch(signature):
        return _deny("invalid_signature", "PET-02-05", instruction_id, target)

    unsigned = dict(envelope)
    unsigned.pop("signature", None)
    expected_signature = hmac.new(secret, _canonical(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return _deny("invalid_signature", "PET-02-05", instruction_id, target)
    if target != expected_machine_id:
        return _deny("wrong_target", "PET-02-07", instruction_id, target)
    if expires_at <= current or issued_at > current + future_skew or expires_at <= issued_at:
        return _deny("expired_or_invalid_time", "PET-02-06", instruction_id, target)
    if expires_at - issued_at > maximum_ttl:
        return _deny("ttl_exceeds_policy", "PET-02-06", instruction_id, target)
    if not replay_guard.consume(signer_id, nonce, instruction_id, target, expires_at, current):
        return _deny("replayed_instruction", "PET-02-08", instruction_id, target)
    return InstructionDecision(True, "accepted", "PET-02-05", instruction_id, target)


def _parse(envelope: Mapping[str, Any]) -> tuple[str, str, str, str, datetime, datetime, str] | InstructionDecision:
    try:
        instruction_id = str(envelope["instruction_id"])
        nonce = str(envelope["nonce"])
        signer_id = str(envelope["signer_id"])
        target = str(envelope["target_machine_id"])
        signature = str(envelope["signature"])
        issued_at = _parse_time(envelope["issued_at"])
        expires_at = _parse_time(envelope["expires_at"])
        payload = envelope["payload"]
    except (KeyError, TypeError, ValueError):
        return _deny("malformed_instruction", "PET-02-04")
    if (
        not _ID_PATTERN.fullmatch(instruction_id)
        or not _ID_PATTERN.fullmatch(nonce)
        or not _ID_PATTERN.fullmatch(signer_id)
        or not _ID_PATTERN.fullmatch(target)
        or not isinstance(payload, dict)
        or not payload
    ):
        return _deny("malformed_instruction", "PET-02-04", instruction_id, target)
    return instruction_id, nonce, signer_id, target, issued_at, expires_at, signature


def _deny(code: str, feature_id: str, instruction_id: str | None = None, target: str | None = None) -> InstructionDecision:
    return InstructionDecision(False, code, feature_id, instruction_id, target)


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return _utc(parsed)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timezone-aware datetime is required")
    return value.astimezone(timezone.utc)


def _validate_secret(secret: bytes) -> None:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("instruction signing secret must contain at least 32 bytes")
