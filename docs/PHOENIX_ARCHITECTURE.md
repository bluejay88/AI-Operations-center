# Phoenix Architecture

Phoenix is the personality, voice, and command interface for the Brain PC. It is not a separate uncontrolled agent. It is a supervised command layer over the existing AI Operations Center database, API, worker queue, and dashboard.

## Purpose

Phoenix should feel like a practical Jarvis-style operator for the Gaming PC:

- Tell the user what each laptop is doing.
- Explain which tasks are queued, running, blocked, or completed.
- Recommend optimizations and next actions.
- Speak morning/hourly/daily reports.
- Coordinate Dev, Research, Business, Finance, Social, Gaming, and Content agents.
- Keep every external or sensitive action behind approval.

## Current Implementation

- Database memory: PostgreSQL tables for machines, agents, tasks, events, heartbeats, connections, reports, and Phoenix events.
- API endpoints: `/phoenix/status` and `/phoenix/briefing`.
- Listener endpoint: `/listener/events` for laptops, AI tools, n8n, Flowise, and other helpers to report work.
- Speaker endpoint: `/speaker/feed/{target_id}` for laptops to pull instructions, approvals, feedback, and Brain guidance.
- Approval endpoint: `/approvals` and `/approvals/{id}/review` for Brain audits.
- CLI commands: `phoenix-status`, `phoenix-brief`, `factory`, `laptop-instructions`, `agent-prompts`.
- Dashboard panel: Phoenix section with a speak button using browser speech synthesis.
- Instruction source: GitHub repo files under `instructions/` and `prompts/`.

## Brain Model

Phoenix reads:

- `readiness_snapshot`: laptop health, task counts, next commands.
- `factory_snapshot`: roles, rubrics, due windows, active tasks.
- `task_snapshot`: current queue.
- `generate_report`: operating summaries.

Phoenix writes:

- `phoenix_events`: command observations, briefings, decisions, and future voice interactions.
- `listener_events`: inbound updates from laptops and external AI helpers.
- `speaker_messages`: outbound instructions and feedback to laptops.
- `approval_requests` and `approval_events`: Brain approval, rejection, requested changes, and deployment records.
- `integration_runs`: supervised calls or routing records for Flowise, n8n, OpenAI, Groq, Claude, Gemini, and future models.

## Approval Logic

Phoenix and the Brain PC should treat every change request as an audit item:

1. Listen for a request.
2. Create an approval request if it can affect code, deployment, money, customers, files, accounts, public content, or legal/finance workflows.
3. Audit for completeness, tests, rollback, risk, security, and revenue/productivity value.
4. Return approval, rejection, or required changes through the speaker feed.
5. Only deploy or implement after approval.

## Voice Upgrade Path

Phase 1 is already local: dashboard speech synthesis reads Phoenix briefings.

Phase 2 should add API-backed natural voice:

- Browser or desktop UI records microphone input.
- Realtime voice session transcribes and responds naturally.
- Phoenix exposes tools for status, tasks, reports, laptop commands, and safe recommendations.
- Sensitive actions return an approval request instead of executing.

Phase 3 should add a desktop shell:

- Start with a local web app running as the Phoenix console.
- Later package it as a Windows desktop app.
- Keep it connected only to localhost/Tailscale endpoints unless explicitly deployed.

## Approval Gates

Phoenix may recommend but may not autonomously perform:

- Sending emails, texts, social posts, or customer messages.
- Spending money, purchasing, bidding, paying bills, or changing accounts.
- Legal filings, LLC changes, tax submissions, or official applications.
- Public deployment of client work.
- Deleting files or credentials.
