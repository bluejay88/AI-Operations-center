from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .settings import Settings


PUBLIC_PATHS = frozenset({"/", "/health", "/dashboard/login"})
PUBLIC_PREFIXES = ("/dashboard", "/laptop-packages")
PBKDF2_ITERATIONS = 600_000


@dataclass(frozen=True)
class Principal:
    principal_id: str
    role: str
    machine_id: str | None = None

    @property
    def is_human_operator(self) -> bool:
        return self.role == "operator"

    @property
    def can_control_fleet(self) -> bool:
        return self.role in {"operator", "brain"}


ANONYMOUS = Principal("anonymous", "anonymous")


def hash_dashboard_password(password: str, *, salt: bytes | None = None) -> str:
    if len(password) < 16:
        raise ValueError("dashboard password must contain at least 16 characters")
    resolved_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), resolved_salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        _b64encode(resolved_salt),
        _b64encode(digest),
    )


def verify_dashboard_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 300_000 or iterations > 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _b64decode(salt_text), iterations)
        return hmac.compare_digest(actual, _b64decode(expected_text))
    except (ValueError, TypeError):
        return False


def issue_dashboard_token(settings: Settings, *, now: int | None = None) -> tuple[str, int]:
    current = int(now or time.time())
    expires_at = current + max(300, min(settings.dashboard_session_ttl_seconds, 43_200))
    payload = {
        "sub": "jayla-operator",
        "role": "operator",
        "iat": current,
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(18),
    }
    encoded = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.dashboard_session_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"v1.{encoded}.{_b64encode(signature)}", expires_at


def verify_dashboard_token(token: str, settings: Settings, *, now: int | None = None) -> Principal | None:
    try:
        version, encoded, signature_text = token.split(".", 2)
        if version != "v1" or len(settings.dashboard_session_secret) < 32:
            return None
        expected = hmac.new(settings.dashboard_session_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_text)):
            return None
        payload = json.loads(_b64decode(encoded))
        current = int(now or time.time())
        if payload.get("role") != "operator" or int(payload.get("exp", 0)) <= current:
            return None
        if int(payload.get("iat", current + 1)) > current + 60:
            return None
        return Principal(str(payload.get("sub") or "jayla-operator"), "operator")
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def validate_security_settings(settings: Settings) -> None:
    if not settings.control_plane_auth_required:
        return
    missing = []
    if len(settings.api_control_token) < 32:
        missing.append("API_CONTROL_TOKEN")
    if len(settings.dashboard_session_secret) < 32:
        missing.append("DASHBOARD_SESSION_SECRET")
    if not settings.dashboard_password_hash:
        missing.append("DASHBOARD_PASSWORD_HASH")
    broker_keys = settings.ssh_broker_envelope_keys()
    for machine_id in ("dev-laptop", "research-laptop", "business-laptop"):
        if machine_id not in broker_keys:
            missing.append(f"SSH_BROKER_ENVELOPE_KEYS_JSON[{machine_id}]")
    if missing:
        raise RuntimeError("Production control-plane authentication is missing: " + ", ".join(missing))


class ControlPlaneAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request.state.principal = ANONYMOUS
        if not self.settings.control_plane_auth_required or _is_public(request):
            return await call_next(request)

        principal = authenticate_request(request, self.settings)
        if principal is None:
            return JSONResponse(
                {"detail": "authentication required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )
        if principal.role == "device" and not _device_route_allowed(request, principal):
            return JSONResponse({"detail": "device role is not authorized for this route"}, status_code=403)
        request.state.principal = principal
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        return response


def authenticate_request(request: Request, settings: Settings) -> Principal | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if len(settings.api_control_token) >= 32 and hmac.compare_digest(token, settings.api_control_token):
        return Principal("brain-gaming-pc", "brain", "brain-gaming-pc")
    dashboard = verify_dashboard_token(token, settings)
    if dashboard:
        return dashboard
    machine_id = request.headers.get("x-ai-ops-device-id", "").strip()
    expected = settings.device_api_tokens().get(machine_id)
    if expected and hmac.compare_digest(token, expected):
        return Principal(machine_id, "device", machine_id)
    return None


def principal_for(request: Request) -> Principal:
    return getattr(request.state, "principal", ANONYMOUS)


def require_fleet_controller(request: Request) -> Principal:
    principal = principal_for(request)
    if request.app.state.settings.control_plane_auth_required and not principal.can_control_fleet:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="fleet-controller authorization required")
    return principal


def require_human_operator(request: Request) -> Principal:
    principal = principal_for(request)
    if request.app.state.settings.control_plane_auth_required and not principal.is_human_operator:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="human operator authorization required")
    return principal


def enforce_device_identity(request: Request, claimed_machine_id: str) -> None:
    principal = principal_for(request)
    if principal.role == "device" and principal.machine_id != claimed_machine_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="device may act only for its own machine identity")


def _is_public(request: Request) -> bool:
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return True
    return any(request.url.path == prefix or request.url.path.startswith(prefix + "/") for prefix in PUBLIC_PREFIXES)


def _device_route_allowed(request: Request, principal: Principal) -> bool:
    path = request.url.path
    method = request.method
    if method == "GET" and path in {"/status", "/readiness.json", "/llm-mesh/status"}:
        return True
    if method == "GET" and path in {
        "/tasks", "/ops2/noc", "/approvals", "/remote-ops", "/collaboration",
        "/pet-machine-capabilities/contracts",
    }:
        return True
    if method == "GET" and path == f"/speaker/feed/{principal.machine_id}":
        return True
    if method == "GET" and path == f"/laptop-agents/{principal.machine_id}/contract":
        return True
    if method == "GET" and path == f"/laptop-agents/{principal.machine_id}/prompt":
        return True
    if method == "POST" and (
        path == "/listener/events"
        or path == "/connections"
        or path == "/ops2/device-telemetry"
        or path == "/ops2/workstation-updates"
        or path == "/llm-mesh/route"
        or path == "/llm-mesh/query"
        or path == "/pet-machine-capabilities/receipts"
        or path == "/pet-performance/samples"
        or path == "/team-chat/post"
        or path == "/project-intake/import-scan"
        or path == "/tasks"
        or path == "/models/query"
        or path.startswith("/models/query/") and path.endswith("/cancel")
        or path == "/remote-ops"
        or path == "/pet-machine-capabilities/requests"
        or path == "/pet-action-proposals"
        or path.startswith("/pet-action-proposals/") and path.endswith("/confirm")
        or path.startswith("/collaboration/peer-requests/") and path.endswith("/respond")
        or path.startswith("/speaker/messages/") and path.endswith("/ack")
    ):
        return True
    return False


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
