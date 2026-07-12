# AI Operations Center

Distributed AI workforce for productivity, revenue operations, research, development, finance, content, and reporting.

This repository is the control plane for a four-machine setup:

- **Gaming PC / Brain**: orchestrator, database, API, reports, Open WebUI, n8n, Ollama, GitHub sync.
- **Laptop A / Business AI**: email, calendar, CRM, invoices, bookkeeping, grants, customer support.
- **Laptop B / Research AI**: grants, real estate, resale, gaming trends, AI news, market opportunities.
- **Laptop C / Development AI**: websites, Python, React, apps, APIs, testing, deployment, security, docs.

The first target is a disciplined 18-agent workforce. The architecture is designed to expand toward 100 agents after the workflows, metrics, approvals, and revenue loops are stable.

## What This Implements

- Agent registry with roles, goals, guardrails, tools, schedules, and assigned machines.
- Orchestrator that creates daily priorities, dispatches tasks, records results, and generates reports.
- Scalable PostgreSQL schema for agents, tasks, runs, ideas, metrics, reports, events, and laptop heartbeats.
- Worker mode for each laptop role.
- Docker Compose stack for PostgreSQL, Ollama, Open WebUI, n8n, and the AI Operations API.
- Morning, hourly, daily, weekly, monthly, and quarterly report scaffolding.
- Revenue-focused idea pipeline targeting passive and service income opportunities.
- GitHub-ready repository structure.

## Quick Start

1. Copy `.env.example` to `.env` and adjust values.
2. Install Docker Desktop on every machine.
3. Install Tailscale on every machine and put them on the same tailnet.
4. On the Gaming PC, run:

```powershell
docker compose up --build
```

5. On each laptop, set `WORKER_MACHINE_ID` in `.env`, then run:

On the brain PC, if Docker Desktop or WSL is missing, run:

```powershell
docker\install-brain-prereqs.ps1
```

Approve the Administrator prompt, then restart Windows if requested.
After restart, open Docker Desktop once and let it finish first-run setup.

```powershell
docker compose --profile worker up --build worker
```

6. Open:

- API: `http://localhost:8088`
- Open WebUI: `http://localhost:3000`
- n8n cloud: `https://aioperation.app.n8n.cloud`
- local n8n fallback: `http://localhost:5678`
- local Flowise fallback: `http://localhost:3001`

## Local Python Setup

If you want to run the CLI outside Docker:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

## Flowise URL

To configure Flowise cloud, copy the base URL from the Flowise browser tab. Use only the protocol and domain, not the `/canvas/...` or `/chatflow/...` path.

## Common Commands

```powershell
python -m ai_ops_center.cli init-db
python -m ai_ops_center.cli seed
python -m ai_ops_center.cli report morning
python -m ai_ops_center.cli report hourly
python -m ai_ops_center.cli status
python -m ai_ops_center.cli worker --machine business-laptop
python -m ai_ops_center.cli worker --machine research-laptop
python -m ai_ops_center.cli worker --machine dev-laptop
```

## Safety Model

Agents can propose, draft, research, test, and report by default. Actions involving money movement, legal filings, sending emails, deploying production changes, or publishing content should require human approval until you explicitly enable automation for that workflow.

## Repository Layout

```text
ai_ops_center/       Core Python orchestration package
config/              Agent, machine, and revenue strategy definitions
docker/              Container entrypoints and service helpers
docs/                Operating guides and expansion plans
sql/                 PostgreSQL schema
tests/               Smoke tests
```
