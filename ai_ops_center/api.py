from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path
import hmac
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .approval_processor import process_approval_queue
from .approvals import approval_detail, approval_snapshot, create_approval_request, review_approval_request
from .brain_bus import acknowledge_speaker_message, create_speaker_message, listener_snapshot, speaker_feed, submit_listener_event
from .business_os import business_os_snapshot, enterprise_org_snapshot, laptop_setup_prompt, seed_autonomous_business_os, seed_enterprise_departments
from .collaboration import (
    collaboration_snapshot,
    create_laptop_handoff,
    create_laptop_model_session,
    create_peer_request,
    request_remote_assist,
    respond_to_peer_request,
)
from .connectivity import connection_snapshot, connection_summary, record_connection
from .factory import factory_snapshot, redistribute_business_queue
from .enterprise_features import enterprise_feature_catalog, seed_enterprise_feature_backlog
from .flowise import healthcheck as flowise_healthcheck
from .flowise import predict as flowise_predict
from .health import machine_status
from .codex_handoff import codex_handoff_packet
from .github_defaults import github_defaults_dict
from .integrations import dispatch_to_provider, integration_status, provider_health
from .model_router import model_solution_snapshot, submit_model_query
from .model_workflows import run_external_model_workflow
from .migrations import apply_migrations, migration_status
from .node_mesh import node_mesh_snapshot
from .orchestrator import create_daily_priorities
from .ops2 import (
    create_notification,
    export_bundle,
    import_bundle,
    noc_snapshot,
    project_context,
    publish_device_telemetry,
    publish_workstation_update,
    seed_operations_2,
    seed_improvement_backlog,
    seed_laptop_work_batches,
    seed_expansion_backlog,
    seed_business_launches,
    split_project,
)
from .operator_requests import create_operator_request, operator_request_snapshot
from .failover import evaluate_failover, evaluate_stale_workers, failover_recommendation
from .phoenix import phoenix_briefing, phoenix_snapshot
from .queue_manager import queue_health, steward_queue
from .readiness import readiness_report, readiness_snapshot
from .remote_ops import remote_operation_snapshot, request_remote_operation, update_remote_operation_from_approval
from .registry import registry_snapshot
from .reports import generate_report
from .security_guardian import security_guardian_audit
from .settings import get_settings
from .tasks import create_business_continuity, create_dev_kickoff, create_chat_task_intake, create_manual_task, task_accounting_audit, task_detail, task_snapshot, task_summary

settings = get_settings()
docs_url = "/docs" if settings.expose_api_docs or settings.app_env != "production" else None
redoc_url = "/redoc" if settings.expose_api_docs or settings.app_env != "production" else None
openapi_url = "/openapi.json" if settings.expose_api_docs or settings.app_env != "production" else None

app = FastAPI(
    title="AI Operations Center",
    version="0.1.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)
logger = logging.getLogger(__name__)
_queue_steward_task: asyncio.Task | None = None
ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
LAPTOP_PACKAGES_DIR = ROOT / "laptop_packages"

cors_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-AI-Ops-Dashboard-Token"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        return response


async def _queue_steward_loop() -> None:
    interval = max(2, int(os.getenv("AI_OPS_QUEUE_STEWARD_SECONDS", "5")))
    while True:
        try:
            await asyncio.to_thread(steward_queue)
        except Exception:
            logger.exception("Queue steward sweep failed")
        await asyncio.sleep(interval)


@app.on_event("startup")
async def start_queue_steward() -> None:
    global _queue_steward_task
    await asyncio.to_thread(apply_migrations)
    if os.getenv("AI_OPS_QUEUE_STEWARD_ENABLED", "true").strip().lower() not in {"0", "false", "no"}:
        _queue_steward_task = asyncio.create_task(_queue_steward_loop())


@app.on_event("shutdown")
async def stop_queue_steward() -> None:
    global _queue_steward_task
    if _queue_steward_task:
        _queue_steward_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _queue_steward_task
        _queue_steward_task = None


app.add_middleware(SecurityHeadersMiddleware)


class FlowisePredictionRequest(BaseModel):
    chatflow_id: str
    question: str
    override_config: dict | None = None


class DashboardLoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    agent_id: str = Field(min_length=2, max_length=80)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3, max_length=4000)
    priority: int = Field(default=50, ge=1, le=100)
    metadata: dict = Field(default_factory=dict)


class ChatTaskIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=3, max_length=12000)
    requester: str = Field(default="chat", min_length=2, max_length=80)
    priority: int = Field(default=85, ge=1, le=100)


class OperatorRequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str = Field(min_length=3, max_length=180)
    request_body: str = Field(min_length=3, max_length=8000)
    requester: str = Field(default="owner", min_length=2, max_length=80)
    target_machine_id: str | None = None
    target_agent_id: str | None = None
    priority: int = Field(default=70, ge=1, le=100)
    delivery_methods: list[str] = Field(default_factory=lambda: ["dashboard"])
    output_format: str = Field(default="dashboard", min_length=2, max_length=40)
    due_at: str | None = None
    metadata: dict = Field(default_factory=dict)


class ConnectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_machine_id: str = Field(min_length=2, max_length=80)
    target_machine_id: str = Field(min_length=2, max_length=80)
    channel: str = Field(min_length=2, max_length=80)
    status: str = Field(pattern="^(online|offline|degraded|unknown|blocked|auth_failed)$")
    latency_ms: float | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)


class ApprovalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    request_type: str = Field(min_length=3, max_length=80)
    requester_machine_id: str = Field(min_length=2, max_length=80)
    requester_agent_id: str = Field(min_length=2, max_length=80)
    risk_level: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    summary: str = Field(min_length=3, max_length=4000)
    proposed_changes: str = Field(min_length=3, max_length=8000)
    metadata: dict = Field(default_factory=dict)


class ApprovalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(approved|rejected|needs_changes|deployed)$")
    feedback: str = Field(min_length=3, max_length=8000)
    actor: str = Field(default="brain-gaming-pc", min_length=2, max_length=80)
    metadata: dict = Field(default_factory=dict)


class ApprovalProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    actor: str = Field(default="brain-approval-processor", min_length=2, max_length=80)


class ListenerEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(default="machine", min_length=2, max_length=80)
    source_id: str = Field(min_length=2, max_length=120)
    event_type: str = Field(min_length=3, max_length=80)
    subject: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=3, max_length=8000)
    priority: int = Field(default=50, ge=1, le=100)
    metadata: dict = Field(default_factory=dict)


class SpeakerAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(min_length=2, max_length=120)


class RemoteOperationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    machine_id: str = Field(min_length=2, max_length=80)
    requested_by: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    operation_type: str = Field(min_length=2, max_length=80)
    command_summary: str = Field(min_length=3, max_length=4000)
    priority: int = Field(default=50, ge=1, le=100)
    metadata: dict = Field(default_factory=dict)


class LaptopHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_machine_id: str = Field(min_length=2, max_length=80)
    to_machine_id: str = Field(min_length=2, max_length=80)
    task_id: int | None = None
    summary: str = Field(min_length=3, max_length=4000)
    evidence: dict = Field(default_factory=dict)
    requested_by: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    priority: int = Field(default=80, ge=1, le=100)


class LaptopModelSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_id: str = Field(min_length=2, max_length=80)
    purpose: str = Field(min_length=3, max_length=180)
    prompt: str = Field(min_length=3, max_length=12000)
    providers: list[str] = Field(default_factory=list)
    requested_by: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    priority: int = Field(default=80, ge=1, le=100)


class RemoteAssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_id: str = Field(min_length=2, max_length=80)
    assist_type: str = Field(pattern="^(browser|files|dashboard|remote_browser_view|remote_file_browse|open_mini_dashboard)$")
    summary: str = Field(min_length=3, max_length=4000)
    requested_by: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    priority: int = Field(default=88, ge=1, le=100)


class PeerRequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_machine_id: str = Field(min_length=2, max_length=80)
    to_machine_id: str = Field(min_length=2, max_length=80)
    request_type: str = Field(min_length=2, max_length=80)
    subject: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=3, max_length=8000)
    requested_by: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    task_id: int | None = None
    project_id: str | None = None
    priority: int = Field(default=80, ge=1, le=100)
    due_at: str | None = None
    metadata: dict = Field(default_factory=dict)


class PeerRequestResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    responder_machine_id: str = Field(min_length=2, max_length=80)
    response_body: str = Field(min_length=3, max_length=8000)
    status: str = Field(default="fulfilled", pattern="^(in_progress|fulfilled|needs_clarification|rejected)$")
    artifacts: list[str] = Field(default_factory=list)
    quality_score: int | None = Field(default=None, ge=0, le=100)
    metadata: dict = Field(default_factory=dict)


class CodexHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str = Field(default="Analyze the AI Operations Center state and decide the next best implementation steps.", min_length=3, max_length=4000)


class IntegrationDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=2, max_length=80)
    purpose: str = Field(min_length=3, max_length=180)
    prompt: str = Field(min_length=3, max_length=12000)
    task_id: int | None = None
    approval_request_id: int | None = None
    options: dict = Field(default_factory=dict)


class ModelWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=3, max_length=180)
    prompt: str = Field(min_length=3, max_length=12000)
    target_id: str = Field(default="all", min_length=2, max_length=120)
    providers: list[str] = Field(default_factory=list)
    task_id: int | None = None
    priority: int = Field(default=80, ge=1, le=100)
    options: dict = Field(default_factory=dict)


class ModelQueryRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    purpose: str = Field(min_length=3, max_length=180)
    prompt: str = Field(min_length=3, max_length=12000)
    requester: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    target_id: str = Field(default="brain-gaming-pc", min_length=2, max_length=120)
    providers: list[str] = Field(default_factory=list)
    project_id: str | None = None
    task_id: int | None = None
    priority: int = Field(default=80, ge=1, le=100)
    auto_create_tasks: bool = False
    require_approval: bool | None = None
    options: dict = Field(default_factory=dict)


class LaptopPackageDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_ids: list[str] = Field(default_factory=lambda: ["dev-laptop", "research-laptop", "business-laptop"])
    brain_host: str = Field(default="100.70.49.32", min_length=3, max_length=120)
    priority: int = Field(default=92, ge=1, le=100)


class BusinessOsModelSprintRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    purpose: str = Field(default="Improve the autonomous zero-budget business launch system", min_length=3, max_length=180)
    providers: list[str] = Field(default_factory=lambda: ["openai", "groq"])
    priority: int = Field(default=88, ge=1, le=100)


class ProjectSplitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template: str = Field(default="website", min_length=2, max_length=80)


class ImportBundleRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    bundle_type: str
    scope: str | None = None
    project_id: str | None = None
    exported_at: str | None = None
    schema_version: int | None = None
    data: dict = Field(default_factory=dict)


class WorkstationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    machine_id: str = Field(min_length=2, max_length=80)
    update_type: str = Field(min_length=3, max_length=80)
    summary: str = Field(min_length=3, max_length=4000)
    agent_id: str | None = None
    project_id: str | None = None
    task_id: int | None = None
    priority: int = Field(default=50, ge=1, le=100)
    logs: str | None = None
    metrics: dict = Field(default_factory=dict)
    errors: list = Field(default_factory=list)
    recommendations: list = Field(default_factory=list)
    estimated_completion_at: str | None = None
    duration_ms: float | None = None
    resource_consumption: dict = Field(default_factory=dict)
    outcome: str | None = None
    created_by: str = "workstation"


class DeviceTelemetryRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    machine_id: str = Field(min_length=2, max_length=80)
    device_name: str | None = None
    hostname: str | None = None
    operating_system: str | None = None
    cpu: str | None = None
    gpu: str | None = None
    ram_mb: float | None = None
    storage_free_mb: float | None = None
    battery_percent: float | None = None
    current_user: str | None = None
    network_status: str | None = None
    tailscale_status: str | None = None
    current_ai_model: str | None = None
    installed_models: list = Field(default_factory=list)
    active_projects: list = Field(default_factory=list)
    current_tasks: list = Field(default_factory=list)
    idle_percentage: float | None = None
    temperature_c: float | None = None
    load_average: float | None = None
    health_score: int | None = None
    metadata: dict = Field(default_factory=dict)


class FailoverEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    machine_id: str = Field(min_length=2, max_length=80)
    battery_percent: float | None = None
    state: str | None = None
    trigger: str = "manual"
    simulate_only: bool = False


class NotificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: str = Field(min_length=2, max_length=120)
    subject: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=3, max_length=4000)
    channel: str = "dashboard"
    priority: int = Field(default=50, ge=1, le=100)
    category: str = "general"
    project_id: str | None = None
    eta_at: str | None = None
    actions: list = Field(default_factory=lambda: ["acknowledge", "snooze"])
    metadata: dict = Field(default_factory=dict)


def _normalize_workstation_update(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["machine_id"] = str(normalized.get("machine_id") or "unknown-machine")[:80]
    normalized["update_type"] = str(normalized.get("update_type") or "workstation_update")[:80]
    normalized["summary"] = str(normalized.get("summary") or "Workstation update received.")[:4000]
    normalized["agent_id"] = normalized.get("agent_id") or None
    normalized["project_id"] = normalized.get("project_id") or None
    normalized["logs"] = normalized.get("logs") or None
    normalized["outcome"] = normalized.get("outcome") or None
    normalized["created_by"] = normalized.get("created_by") or "workstation"

    try:
        normalized["priority"] = max(1, min(100, int(normalized.get("priority", 50))))
    except (TypeError, ValueError):
        normalized["priority"] = 50

    try:
        normalized["task_id"] = int(normalized["task_id"]) if normalized.get("task_id") is not None else None
    except (TypeError, ValueError):
        normalized["task_id"] = None

    try:
        normalized["duration_ms"] = float(normalized["duration_ms"]) if normalized.get("duration_ms") is not None else None
    except (TypeError, ValueError):
        normalized["duration_ms"] = None

    for field in ("metrics", "resource_consumption"):
        if not isinstance(normalized.get(field), dict):
            normalized[field] = {}

    for field in ("errors", "recommendations"):
        value = normalized.get(field)
        if value is None:
            normalized[field] = []
        elif isinstance(value, list):
            normalized[field] = value
        else:
            normalized[field] = [value]

    return normalized


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/dashboard/login")
def dashboard_login(request: DashboardLoginRequest) -> dict[str, str | bool]:
    expected = settings.dashboard_password
    submitted = request.password.strip()
    if expected and not hmac.compare_digest(submitted, expected.strip()):
        return {"ok": False, "message": "Invalid dashboard password"}
    return {"ok": True, "token": "dashboard-session", "message": "Dashboard unlocked"}


@app.get("/status")
def status() -> dict[str, str]:
    return {"status": machine_status()}


@app.get("/endpoints")
def endpoint_contract() -> dict:
    base = "http://100.70.49.32:8088"
    endpoints = [
        {"name": "Health", "method": "GET", "path": "/health", "purpose": "Verify Brain API is reachable."},
        {"name": "Realtime stream", "method": "GET", "path": "/stream", "purpose": "SSE stream for readiness, tasks, connections, approvals, listener, speaker, integrations, and model solutions."},
        {"name": "Device telemetry", "method": "POST", "path": "/ops2/device-telemetry", "purpose": "Laptop heartbeat, hardware, battery, model, workload, and health telemetry."},
        {"name": "Connections", "method": "POST", "path": "/connections", "purpose": "Report Tailscale, SSH, API, listener, speaker, and worker connectivity."},
        {"name": "Tasks", "method": "GET", "path": "/tasks", "purpose": "Read assigned and global queue items."},
        {"name": "Task intake", "method": "POST", "path": "/tasks/intake", "purpose": "Submit chat/request work for Brain routing."},
        {"name": "Listener events", "method": "POST", "path": "/listener/events", "purpose": "Publish laptop progress, logs, errors, recommendations, and requests to the Brain."},
        {"name": "Listener snapshot", "method": "GET", "path": "/listener/events", "purpose": "Read recent inbound workstation and workflow events."},
        {"name": "Speaker feed", "method": "GET", "path": "/speaker/feed/{machine_id}", "purpose": "Pull Brain assignments, approvals, feedback, and package install instructions."},
        {"name": "Speaker ack", "method": "POST", "path": "/speaker/messages/{message_id}/ack", "purpose": "Acknowledge a Brain message after the laptop has consumed it."},
        {"name": "Approvals", "method": "GET", "path": "/approvals", "purpose": "Read outstanding and completed approval requests with Brain score/rating."},
        {"name": "Create approval", "method": "POST", "path": "/approvals", "purpose": "Request approval for sensitive or high-impact changes."},
        {"name": "Brain approval processor", "method": "POST", "path": "/approvals/process", "purpose": "Have the Brain review pending approvals and return approve/needs_changes/reject decisions."},
        {"name": "Human approval review", "method": "POST", "path": "/approvals/{request_id}/review", "purpose": "Jayla or Brain manually approves, rejects, cycles back, or marks deployed."},
        {"name": "Remote operations", "method": "POST", "path": "/remote-ops", "purpose": "Request approved remote actions such as opening dashboards, builds, tests, browser/file assist, or service restarts."},
        {"name": "Remote operations queue", "method": "GET", "path": "/remote-ops", "purpose": "Read approved, pending, queued, rejected, and completed remote requests."},
        {"name": "Collaboration handoff", "method": "POST", "path": "/collaboration/handoff", "purpose": "Pass approved work between laptops with evidence rubric."},
        {"name": "Peer request", "method": "POST", "path": "/collaboration/peer-requests", "purpose": "Route laptop-to-laptop asks for research, assets, QA, security review, stats, diagnostics, and handoff help through the Brain bus."},
        {"name": "Peer response", "method": "POST", "path": "/collaboration/peer-requests/{request_id}/respond", "purpose": "Return peer work, artifacts, quality score, and status back to the requesting laptop through the speaker/listener bus."},
        {"name": "Node mesh contract", "method": "GET", "path": "/node-mesh", "purpose": "Read Brain Mesh node roles, peer permissions, message channels, task states, and the standard handoff envelope."},
        {"name": "Migration status", "method": "GET", "path": "/migrations", "purpose": "Read applied and pending database migrations before an update."},
        {"name": "Apply migrations", "method": "POST", "path": "/migrations/apply", "purpose": "Apply pending versioned migrations with checksums after Git updates."},
        {"name": "Laptop model session", "method": "POST", "path": "/collaboration/model-session", "purpose": "Ask a laptop team to consult configured models and report back."},
        {"name": "Model query", "method": "POST", "path": "/models/query", "purpose": "Pipe prompts into configured model mesh for recommendations and task routing."},
        {"name": "Model workflow", "method": "POST", "path": "/integrations/workflow", "purpose": "Run external model workflow and publish results to listener/speaker."},
        {"name": "Enterprise feature catalog", "method": "GET", "path": "/enterprise-features", "purpose": "Read the 500-feature Brain PC enterprise roadmap grouped by domain, owner, laptop, and approval policy."},
        {"name": "Seed enterprise features", "method": "POST", "path": "/enterprise-features/seed", "purpose": "Create deduped backlog tasks for the 500 enterprise enhancements with audit records and approval gating."},
        {"name": "NOC", "method": "GET", "path": "/ops2/noc", "purpose": "Enterprise dashboard data for workforce, projects, infrastructure, AI metrics, security, reports, and KPIs."},
        {"name": "Laptop packages", "method": "GET", "path": "/laptop-packages", "purpose": "List laptop-specific AI Operations Center Node Console packages."},
        {"name": "Laptop package dispatch", "method": "POST", "path": "/laptop-packages/dispatch", "purpose": "Send install/update instructions to each laptop speaker feed."},
    ]
    return {
        "base_url": base,
        "security": {
            "network": "Tailscale-only private 100.64.0.0/10 access is the expected transport.",
            "ssh": "Key-only SSH is preferred; sensitive actions require approval and audit records.",
            "approval_policy": "Money, legal, credentials, public posting/sending, deployment, browser/file control, and destructive actions require Brain/Jayla approval.",
        },
        "ports": {"brain_api": 8088, "ssh": 22, "dashboard": 8088},
        "endpoints": endpoints,
    }


@app.get("/registry")
def registry() -> dict:
    return registry_snapshot()


@app.get("/factory")
def factory() -> dict:
    return factory_snapshot()


@app.get("/node-mesh")
def node_mesh() -> dict:
    return node_mesh_snapshot()


@app.get("/migrations")
def migrations() -> dict:
    return migration_status()


@app.post("/migrations/apply")
def migrations_apply() -> dict:
    return apply_migrations()


@app.get("/phoenix/status")
def phoenix_status() -> dict:
    return phoenix_snapshot()


@app.get("/phoenix/briefing")
def phoenix_brief() -> dict[str, str]:
    return {"briefing": phoenix_briefing()}


@app.get("/readiness")
def readiness() -> dict[str, str]:
    return {"readiness": readiness_report()}


@app.get("/readiness.json")
def readiness_json() -> dict:
    return readiness_snapshot()


@app.get("/stream")
async def stream() -> StreamingResponse:
    import asyncio
    import json

    async def events():
        while True:
            recent_tasks = task_snapshot()
            lifetime_tasks = task_summary()
            live_connections = connection_snapshot()
            live_readiness = readiness_snapshot()
            live_readiness["task_summary"] = lifetime_tasks
            for machine in live_readiness.get("machines", []):
                counts = dict(lifetime_tasks["by_machine"].get(machine.get("id"), {}))
                machine["task_counts"] = counts
                machine["lifetime_task_counts"] = counts
                machine["completed_tasks_total"] = int(counts.get("completed", 0))
            payload = {
                "readiness": live_readiness,
                "tasks": recent_tasks,
                "task_summary": lifetime_tasks,
                "task_accounting_audit": task_accounting_audit(
                    lifetime_tasks,
                    recent_returned=len(recent_tasks),
                    readiness_summary=live_readiness["task_summary"],
                ),
                "queue_health": queue_health(),
                "task_list": {"limit": 50, "returned": len(recent_tasks), "scope": "recent_prioritized"},
                "connections": live_connections,
                "connection_summary": connection_summary(live_connections),
                "factory": factory_snapshot(),
                "approvals": approval_snapshot(limit=20),
                "listener": {"events": listener_snapshot(limit=20)},
                "speaker": speaker_feed("brain-gaming-pc"),
                "collaboration": collaboration_snapshot(limit=20),
                "integrations": integration_status(),
                "model_solutions": model_solution_snapshot(limit=10),
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/connections")
def connections() -> dict:
    snapshot = connection_snapshot()
    return {"connections": snapshot, "connection_summary": connection_summary(snapshot)}


@app.post("/connections")
def update_connection(request: ConnectionUpdateRequest) -> dict[str, str]:
    record_connection(
        source_machine_id=request.source_machine_id,
        target_machine_id=request.target_machine_id,
        channel=request.channel,
        status=request.status,
        latency_ms=request.latency_ms,
        metadata=request.metadata,
    )
    return {"status": "recorded"}


@app.get("/tasks")
def tasks(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    recent_tasks = task_snapshot(limit=limit)
    lifetime_tasks = task_summary()
    return {
        "tasks": recent_tasks,
        "task_summary": lifetime_tasks,
        "task_accounting_audit": task_accounting_audit(lifetime_tasks, recent_returned=len(recent_tasks)),
        "queue_health": queue_health(),
        "list": {"limit": limit, "returned": len(recent_tasks), "scope": "recent_prioritized"},
    }


@app.get("/queue/health")
def queue_health_endpoint() -> dict:
    return queue_health()


@app.post("/queue/steward")
def queue_steward_endpoint(max_moves: int = Query(default=50, ge=1, le=500)) -> dict:
    return steward_queue(max_moves=max_moves)


@app.get("/tasks/{task_id}")
def task_by_id(task_id: int) -> dict:
    task = task_detail(task_id)
    return {"task": task}


@app.post("/tasks")
def create_task(request: TaskCreateRequest) -> dict[str, int]:
    task_id = create_manual_task(
        title=request.title,
        agent_id=request.agent_id,
        category=request.category,
        description=request.description,
        priority=request.priority,
        metadata=request.metadata,
    )
    return {"task_id": task_id}


@app.post("/tasks/intake")
def chat_task_intake(request: ChatTaskIntakeRequest) -> dict[str, list[int]]:
    return {
        "created_task_ids": create_chat_task_intake(
            title=request.title,
            body=request.body,
            requester=request.requester,
            priority=request.priority,
        )
    }


@app.get("/operator-requests")
def operator_requests() -> dict:
    return {"requests": operator_request_snapshot()}


@app.post("/operator-requests")
def create_operator_request_api(request: OperatorRequestCreateRequest) -> dict:
    return create_operator_request(request.model_dump())


@app.get("/approvals")
def approvals() -> dict:
    return {"approvals": approval_snapshot()}


@app.post("/approvals")
def create_approval(request: ApprovalCreateRequest) -> dict[str, int]:
    request_id = create_approval_request(
        title=request.title,
        request_type=request.request_type,
        requester_machine_id=request.requester_machine_id,
        requester_agent_id=request.requester_agent_id,
        risk_level=request.risk_level,
        summary=request.summary,
        proposed_changes=request.proposed_changes,
        metadata=request.metadata,
    )
    return {"approval_request_id": request_id}


@app.post("/approvals/process")
def process_approvals(request: ApprovalProcessRequest) -> dict:
    return process_approval_queue(limit=request.limit, actor=request.actor)


@app.get("/approvals/{request_id}")
def approval(request_id: int) -> dict:
    detail = approval_detail(request_id)
    return {"approval": detail}


@app.post("/approvals/{request_id}/review")
def review_approval(request_id: int, request: ApprovalReviewRequest) -> dict:
    reviewed = review_approval_request(request_id, request.decision, request.feedback, request.actor, request.metadata)
    approval_metadata = dict(reviewed.get("metadata") or {})
    remote_operation_id = approval_metadata.get("remote_operation_request_id")
    if remote_operation_id:
        update_remote_operation_from_approval(int(remote_operation_id), request.decision, request.feedback)
    requester_machine = reviewed.get("requester_machine_id")
    if requester_machine:
        create_speaker_message(
            target_id=requester_machine,
            message_type=f"approval_{request.decision}",
            subject=f"Brain review: {reviewed['title']}",
            body=request.feedback,
            priority=90 if request.decision in {"approved", "needs_changes"} else 70,
            metadata={"approval_request_id": request_id, "decision": request.decision},
        )
    return {"approval": reviewed}


@app.get("/listener/events")
def listener_events() -> dict:
    return {"events": listener_snapshot()}


@app.post("/listener/events")
def listener_event(request: ListenerEventRequest) -> dict:
    return submit_listener_event(
        source_type=request.source_type,
        source_id=request.source_id,
        event_type=request.event_type,
        subject=request.subject,
        body=request.body,
        priority=request.priority,
        metadata=request.metadata,
    )


@app.get("/speaker/feed/{target_id}")
def speaker(target_id: str, include_acknowledged: bool = False) -> dict:
    return speaker_feed(target_id, include_acknowledged=include_acknowledged)


@app.post("/speaker/messages/{message_id}/ack")
def speaker_ack(message_id: int, request: SpeakerAckRequest) -> dict:
    return {"message": acknowledge_speaker_message(message_id, request.actor)}


@app.get("/remote-ops")
def remote_ops() -> dict:
    return {"requests": remote_operation_snapshot()}


@app.post("/remote-ops")
def create_remote_ops(request: RemoteOperationRequest) -> dict:
    return request_remote_operation(
        machine_id=request.machine_id,
        requested_by=request.requested_by,
        operation_type=request.operation_type,
        command_summary=request.command_summary,
        priority=request.priority,
        metadata=request.metadata,
    )


@app.get("/collaboration")
def collaboration() -> dict:
    return collaboration_snapshot()


@app.post("/collaboration/peer-requests")
def collaboration_peer_request(request: PeerRequestCreateRequest) -> dict:
    return create_peer_request(
        from_machine_id=request.from_machine_id,
        to_machine_id=request.to_machine_id,
        request_type=request.request_type,
        subject=request.subject,
        body=request.body,
        requested_by=request.requested_by,
        task_id=request.task_id,
        project_id=request.project_id,
        priority=request.priority,
        due_at=request.due_at,
        metadata=request.metadata,
    )


@app.post("/collaboration/peer-requests/{request_id}/respond")
def collaboration_peer_response(request_id: int, request: PeerRequestResponseRequest) -> dict:
    return respond_to_peer_request(
        request_id=request_id,
        responder_machine_id=request.responder_machine_id,
        response_body=request.response_body,
        status=request.status,
        artifacts=request.artifacts,
        quality_score=request.quality_score,
        metadata=request.metadata,
    )


@app.post("/collaboration/handoff")
def laptop_handoff(request: LaptopHandoffRequest) -> dict:
    return create_laptop_handoff(
        from_machine_id=request.from_machine_id,
        to_machine_id=request.to_machine_id,
        task_id=request.task_id,
        summary=request.summary,
        evidence=request.evidence,
        requested_by=request.requested_by,
        priority=request.priority,
    )


@app.post("/collaboration/model-session")
def laptop_model_session(request: LaptopModelSessionRequest) -> dict:
    return create_laptop_model_session(
        machine_id=request.machine_id,
        purpose=request.purpose,
        prompt=request.prompt,
        providers=request.providers or None,
        requested_by=request.requested_by,
        priority=request.priority,
    )


@app.post("/remote-assist")
def remote_assist(request: RemoteAssistRequest) -> dict:
    return request_remote_assist(
        machine_id=request.machine_id,
        assist_type=request.assist_type,
        summary=request.summary,
        requested_by=request.requested_by,
        priority=request.priority,
    )


@app.get("/security/guardian")
def security_guardian() -> dict:
    return security_guardian_audit()


@app.post("/orchestrator/daily-priorities")
def daily_priorities() -> dict[str, list[int]]:
    return {"created_task_ids": create_daily_priorities()}


@app.post("/orchestrator/dev-kickoff")
def dev_kickoff() -> dict[str, list[int]]:
    return {"created_task_ids": create_dev_kickoff()}


@app.post("/orchestrator/business-continuity")
def business_continuity() -> dict[str, list[int]]:
    return {"created_task_ids": create_business_continuity()}


@app.post("/orchestrator/redistribute-business-queue")
def redistribute_business() -> dict:
    return {"reassigned": redistribute_business_queue()}


@app.get("/reports/{report_type}")
def report(report_type: str) -> dict[str, str]:
    return {"report": generate_report(report_type)}


@app.get("/integrations/flowise/health")
async def flowise_health() -> dict:
    return await flowise_healthcheck()


@app.post("/integrations/flowise/predict")
async def flowise_prediction(request: FlowisePredictionRequest) -> dict:
    return await flowise_predict(request.chatflow_id, request.question, request.override_config)


@app.get("/integrations/status")
def integrations_status() -> dict:
    return integration_status()


@app.get("/github/defaults")
def github_defaults_api() -> dict[str, str]:
    return github_defaults_dict()


@app.get("/codex/handoff")
def codex_handoff() -> dict:
    return codex_handoff_packet()


@app.post("/codex/handoff")
def create_codex_handoff(request: CodexHandoffRequest) -> dict:
    return codex_handoff_packet(prompt=request.prompt)


@app.get("/integrations/health")
async def integrations_health() -> dict:
    return await provider_health()


@app.post("/integrations/dispatch")
async def integrations_dispatch(request: IntegrationDispatchRequest) -> dict:
    return await dispatch_to_provider(
        provider=request.provider,
        purpose=request.purpose,
        prompt=request.prompt,
        task_id=request.task_id,
        approval_request_id=request.approval_request_id,
        options=request.options,
    )


@app.post("/integrations/workflow")
async def integrations_workflow(request: ModelWorkflowRequest) -> dict:
    return await run_external_model_workflow(
        purpose=request.purpose,
        prompt=request.prompt,
        target_id=request.target_id,
        providers=request.providers or None,
        task_id=request.task_id,
        priority=request.priority,
        options=request.options,
    )


@app.get("/models/solutions")
def model_solutions() -> dict:
    return {"solutions": model_solution_snapshot()}


@app.post("/models/query")
async def models_query(request: ModelQueryRequest) -> dict:
    return await submit_model_query(
        purpose=request.purpose,
        prompt=request.prompt,
        requester=request.requester,
        target_id=request.target_id,
        providers=request.providers or None,
        project_id=request.project_id,
        task_id=request.task_id,
        priority=request.priority,
        auto_create_tasks=request.auto_create_tasks,
        require_approval=request.require_approval,
        options=request.options,
    )


@app.get("/laptop-packages")
def laptop_packages() -> dict:
    packages = []
    if LAPTOP_PACKAGES_DIR.exists():
        for package_dir in sorted(LAPTOP_PACKAGES_DIR.iterdir()):
            if package_dir.is_dir() and (package_dir / "index.html").exists():
                packages.append(
                    {
                        "machine_id": package_dir.name,
                        "dashboard_url": f"/laptop-packages/{package_dir.name}/index.html",
                        "install_script": f"laptop_packages\\{package_dir.name}\\install.ps1",
                    }
                )
    return {"packages": packages}


@app.post("/laptop-packages/dispatch")
def dispatch_laptop_packages(request: LaptopPackageDispatchRequest) -> dict:
    messages = []
    for machine_id in request.machine_ids:
        install_command = (
            "git pull origin master; "
            f"powershell -ExecutionPolicy Bypass -File .\\laptop_packages\\{machine_id}\\install.ps1 -BrainHost {request.brain_host}"
        )
        message_id = create_speaker_message(
            target_id=machine_id,
            message_type="laptop_package_install",
            subject=f"Install AI Ops Node Console package for {machine_id}",
            body=(
                "Pull the latest AI Operations Center repo, then run the laptop-specific Node Console package. "
                "This opens the local dashboard, publishes heartbeat telemetry, reads the Brain speaker feed, and keeps the PET companion and Shield visible.\n\n"
                f"Command:\n{install_command}"
            ),
            priority=request.priority,
            metadata={"machine_id": machine_id, "brain_host": request.brain_host, "install_command": install_command},
        )
        messages.append({"machine_id": machine_id, "speaker_message_id": message_id, "install_command": install_command})
    return {"dispatched": messages}


@app.get("/business-os")
def business_os() -> dict:
    return business_os_snapshot()


@app.post("/business-os/seed")
def business_os_seed() -> dict:
    business = seed_autonomous_business_os()
    departments = seed_enterprise_departments()
    return {"business_os": business, "enterprise_org": departments}


@app.get("/business-os/laptop-setup/{machine_id}")
def business_os_laptop_setup(machine_id: str) -> dict:
    return {"machine_id": machine_id, "prompt": laptop_setup_prompt(machine_id)}


@app.get("/enterprise-org")
def enterprise_org() -> dict:
    return enterprise_org_snapshot()


@app.post("/enterprise-org/seed")
def enterprise_org_seed() -> dict:
    return seed_enterprise_departments()


@app.get("/enterprise-features")
def enterprise_features() -> dict:
    return enterprise_feature_catalog()


@app.post("/enterprise-features/seed")
def enterprise_features_seed() -> dict:
    return seed_enterprise_feature_backlog()


@app.post("/business-os/model-sprint")
async def business_os_model_sprint(request: BusinessOsModelSprintRequest) -> dict:
    prompt = (
        "Review Jayla's Autonomous Business OS. Improve the zero-budget path to approved online businesses, "
        "the CEO/department model, laptop division of labor, security guardrails, and 30-60 day profitability validation. "
        "Do not recommend spending, legal filings, banking, public sending, or external deployment without Jayla approval."
    )
    return await submit_model_query(
        purpose=request.purpose,
        prompt=prompt,
        requester="brain-gaming-pc",
        target_id="brain-gaming-pc",
        providers=request.providers,
        priority=request.priority,
        auto_create_tasks=False,
        require_approval=False,
        options={"max_tokens": 500},
    )


@app.get("/ops2/noc")
def ops2_noc() -> dict:
    return noc_snapshot()


@app.post("/ops2/seed")
def ops2_seed() -> dict:
    return seed_operations_2()


@app.post("/ops2/improvements/seed")
def ops2_seed_improvements() -> dict:
    return seed_improvement_backlog()


@app.post("/ops2/expansion/seed")
def ops2_seed_expansion(total: int = 400) -> dict:
    return seed_expansion_backlog(total=total)


@app.post("/ops2/business-launches/seed")
def ops2_seed_business_launches() -> dict:
    return seed_business_launches()


@app.post("/ops2/laptop-work/seed")
def ops2_seed_laptop_work(tasks_per_laptop: int = 100) -> dict:
    return seed_laptop_work_batches(tasks_per_laptop=tasks_per_laptop)


@app.post("/ops2/projects/{project_id}/split")
def ops2_split_project(project_id: str, request: ProjectSplitRequest) -> dict:
    return split_project(project_id, request.template)


@app.get("/ops2/projects/{project_id}/context")
def ops2_project_context(project_id: str) -> dict:
    return project_context(project_id)


@app.get("/ops2/export")
def ops2_export(scope: str = "all", project_id: str = "ai-operations-center-2") -> dict:
    return export_bundle(scope=scope, project_id=project_id)


@app.post("/ops2/import")
def ops2_import(request: ImportBundleRequest) -> dict:
    return import_bundle(request.model_dump())


@app.post("/ops2/workstation-updates")
async def ops2_workstation_update(request: Request) -> dict:
    payload = await request.json()
    if not isinstance(payload, dict):
        payload = {"summary": "Non-object workstation update received.", "raw_payload": payload}
    return publish_workstation_update(_normalize_workstation_update(payload))


@app.post("/ops2/device-telemetry")
def ops2_device_telemetry(request: DeviceTelemetryRequest) -> dict:
    return publish_device_telemetry(request.model_dump())


@app.post("/ops2/failover/evaluate")
def ops2_failover_evaluate(request: FailoverEvaluateRequest) -> dict:
    payload = request.model_dump()
    if payload.get("simulate_only"):
        return {"triggered": False, "recommendation": failover_recommendation(payload["machine_id"], payload.get("battery_percent"), payload.get("state"))}
    return evaluate_failover(
        payload["machine_id"],
        battery_percent=payload.get("battery_percent"),
        state=payload.get("state"),
        trigger=payload.get("trigger", "manual"),
    )


@app.post("/ops2/failover/stale-workers")
def ops2_failover_stale_workers(stale_after_minutes: int = 3) -> dict:
    return evaluate_stale_workers(stale_after_minutes=stale_after_minutes)


@app.post("/ops2/notifications")
def ops2_notification(request: NotificationRequest) -> dict:
    return create_notification(request.model_dump())


if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

if LAPTOP_PACKAGES_DIR.exists():
    app.mount("/laptop-packages", StaticFiles(directory=LAPTOP_PACKAGES_DIR, html=True), name="laptop-packages")
