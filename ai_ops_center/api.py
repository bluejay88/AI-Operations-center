from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .flowise import healthcheck as flowise_healthcheck
from .flowise import predict as flowise_predict
from .orchestrator import create_daily_priorities
from .registry import registry_snapshot
from .reports import generate_report

app = FastAPI(title="AI Operations Center", version="0.1.0")


class FlowisePredictionRequest(BaseModel):
    chatflow_id: str
    question: str
    override_config: dict | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/registry")
def registry() -> dict:
    return registry_snapshot()


@app.post("/orchestrator/daily-priorities")
def daily_priorities() -> dict[str, list[int]]:
    return {"created_task_ids": create_daily_priorities()}


@app.get("/reports/{report_type}")
def report(report_type: str) -> dict[str, str]:
    return {"report": generate_report(report_type)}


@app.get("/integrations/flowise/health")
async def flowise_health() -> dict:
    return await flowise_healthcheck()


@app.post("/integrations/flowise/predict")
async def flowise_prediction(request: FlowisePredictionRequest) -> dict:
    return await flowise_predict(request.chatflow_id, request.question, request.override_config)
