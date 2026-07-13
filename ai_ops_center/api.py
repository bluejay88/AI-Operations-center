from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .approvals import approval_detail, approval_snapshot, create_approval_request, review_approval_request
from .brain_bus import acknowledge_speaker_message, create_speaker_message, listener_snapshot, speaker_feed, submit_listener_event
from .connectivity import connection_snapshot, record_connection
from .factory import factory_snapshot, redistribute_business_queue
from .flowise import healthcheck as flowise_healthcheck
from .flowise import predict as flowise_predict
from .health import machine_status
from .integrations import dispatch_to_provider, integration_status, provider_health
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
    split_project,
)
from .phoenix import phoenix_briefing, phoenix_snapshot
from .readiness import readiness_report, readiness_snapshot
from .registry import registry_snapshot
from .reports import generate_report
from .settings import get_settings
from .tasks import create_business_continuity, create_dev_kickoff, create_manual_task, task_snapshot

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
ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"


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


app.add_middleware(SecurityHeadersMiddleware)


class FlowisePredictionRequest(BaseModel):
    chatflow_id: str
    question: str
    override_config: dict | None = None


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=180)
    agent_id: str = Field(min_length=2, max_length=80)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3, max_length=4000)
    priority: int = Field(default=50, ge=1, le=100)


class ConnectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_machine_id: str = Field(min_length=2, max_length=80)
    target_machine_id: str = Field(min_length=2, max_length=80)
    channel: str = Field(min_length=2, max_length=80)
    status: str = Field(pattern="^(online|offline|degraded|unknown|blocked)$")
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


class IntegrationDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=2, max_length=80)
    purpose: str = Field(min_length=3, max_length=180)
    prompt: str = Field(min_length=3, max_length=12000)
    task_id: int | None = None
    approval_request_id: int | None = None
    options: dict = Field(default_factory=dict)


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


@app.get("/status")
def status() -> dict[str, str]:
    return {"status": machine_status()}


@app.get("/registry")
def registry() -> dict:
    return registry_snapshot()


@app.get("/factory")
def factory() -> dict:
    return factory_snapshot()


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
            payload = {
                "readiness": readiness_snapshot(),
                "tasks": task_snapshot(),
                "connections": connection_snapshot(),
                "factory": factory_snapshot(),
                "approvals": approval_snapshot(limit=20),
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/connections")
def connections() -> dict:
    return {"connections": connection_snapshot()}


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
def tasks() -> dict:
    return {"tasks": task_snapshot()}


@app.post("/tasks")
def create_task(request: TaskCreateRequest) -> dict[str, int]:
    task_id = create_manual_task(
        title=request.title,
        agent_id=request.agent_id,
        category=request.category,
        description=request.description,
        priority=request.priority,
    )
    return {"task_id": task_id}


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


@app.get("/approvals/{request_id}")
def approval(request_id: int) -> dict:
    detail = approval_detail(request_id)
    return {"approval": detail}


@app.post("/approvals/{request_id}/review")
def review_approval(request_id: int, request: ApprovalReviewRequest) -> dict:
    reviewed = review_approval_request(request_id, request.decision, request.feedback, request.actor, request.metadata)
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


@app.get("/ops2/noc")
def ops2_noc() -> dict:
    return noc_snapshot()


@app.post("/ops2/seed")
def ops2_seed() -> dict:
    return seed_operations_2()


@app.post("/ops2/improvements/seed")
def ops2_seed_improvements() -> dict:
    return seed_improvement_backlog()


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


@app.post("/ops2/notifications")
def ops2_notification(request: NotificationRequest) -> dict:
    return create_notification(request.model_dump())


if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
