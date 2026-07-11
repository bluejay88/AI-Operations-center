from __future__ import annotations

from fastapi import FastAPI

from .orchestrator import create_daily_priorities
from .registry import registry_snapshot
from .reports import generate_report

app = FastAPI(title="AI Operations Center", version="0.1.0")


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

