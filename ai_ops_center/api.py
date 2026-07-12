from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .connectivity import connection_snapshot, record_connection
from .flowise import healthcheck as flowise_healthcheck
from .flowise import predict as flowise_predict
from .health import machine_status
from .orchestrator import create_daily_priorities
from .readiness import readiness_report, readiness_snapshot
from .registry import registry_snapshot
from .reports import generate_report
from .settings import get_settings
from .tasks import create_dev_kickoff, create_manual_task, task_snapshot

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def status() -> dict[str, str]:
    return {"status": machine_status()}


@app.get("/registry")
def registry() -> dict:
    return registry_snapshot()


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


@app.post("/orchestrator/daily-priorities")
def daily_priorities() -> dict[str, list[int]]:
    return {"created_task_ids": create_daily_priorities()}


@app.post("/orchestrator/dev-kickoff")
def dev_kickoff() -> dict[str, list[int]]:
    return {"created_task_ids": create_dev_kickoff()}


@app.get("/reports/{report_type}")
def report(report_type: str) -> dict[str, str]:
    return {"report": generate_report(report_type)}


@app.get("/integrations/flowise/health")
async def flowise_health() -> dict:
    return await flowise_healthcheck()


@app.post("/integrations/flowise/predict")
async def flowise_prediction(request: FlowisePredictionRequest) -> dict:
    return await flowise_predict(request.chatflow_id, request.question, request.override_config)


if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
