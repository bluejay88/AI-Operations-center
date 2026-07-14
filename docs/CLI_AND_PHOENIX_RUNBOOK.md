# CLI And Phoenix Runbook

This repo now ships both machine instructions and runnable CLI commands. Every laptop should pull the latest GitHub commit before running worker updates.

## Brain PC Commands

Run from the repo folder on the Brain PC:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli init-db
docker compose run --rm ai-ops-api python -m ai_ops_center.cli seed
docker compose run --rm ai-ops-api python -m ai_ops_center.cli readiness
docker compose run --rm ai-ops-api python -m ai_ops_center.cli factory
docker compose run --rm ai-ops-api python -m ai_ops_center.cli phoenix-brief
docker compose run --rm ai-ops-api python -m ai_ops_center.cli redistribute-business
```

## Laptop Commands

Each laptop can print its own instructions after pulling GitHub.

Development laptop:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli laptop-instructions dev-laptop
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -ApprovedCommit <approved-commit-sha> -BrainApprovalId <review-id>
```

Research laptop:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli laptop-instructions research-laptop
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -ApprovedCommit <approved-commit-sha> -BrainApprovalId <review-id>
```

Business laptop:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli laptop-instructions business-laptop
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -ApprovedCommit <approved-commit-sha> -BrainApprovalId <review-id>
```

If the Business laptop is not cloned yet:

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/bluejay88/AI-Operations-center.git
cd AI-Operations-center
powershell -ExecutionPolicy Bypass -File docker\onboard-laptop.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

## Phoenix Commands

Phoenix is the Brain PC command voice and briefing layer.

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli phoenix-status
docker compose run --rm ai-ops-api python -m ai_ops_center.cli phoenix-brief
docker compose run --rm ai-ops-api python -m ai_ops_center.cli approvals
docker compose run --rm ai-ops-api python -m ai_ops_center.cli integrations
```

Dashboard endpoints:

```text
GET http://localhost:8088/phoenix/status
GET http://localhost:8088/phoenix/briefing
GET http://localhost:8088/approvals
GET http://localhost:8088/listener/events
GET http://localhost:8088/speaker/feed/brain-gaming-pc
GET http://localhost:8088/integrations/status
```

Dashboard UI:

```text
http://localhost:8088/dashboard/#phoenix
http://localhost:8088/dashboard/#brain-bus
```

## Listener/Speaker Loop

Laptops and external AI helpers send updates to:

```text
POST http://100.70.49.32:8088/listener/events
```

The Brain applies routing logic:

- `workload_update` becomes a Brain speaker message.
- `approval_request`, `change_request`, and `deployment_request` become approval requests.
- `task_request` creates a task.
- Other events are logged and surfaced to the Brain PC.

Laptops pull instructions and feedback from:

```text
GET http://100.70.49.32:8088/speaker/feed/dev-laptop
GET http://100.70.49.32:8088/speaker/feed/research-laptop
GET http://100.70.49.32:8088/speaker/feed/business-laptop
```

Approvals are reviewed by the Brain:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli review-approval 1 needs_changes --feedback "Add test output and rollback notes before approval."
docker compose run --rm ai-ops-api python -m ai_ops_center.cli review-approval 1 approved --feedback "Approved for supervised deployment."
docker compose run --rm ai-ops-api python -m ai_ops_center.cli review-approval 1 deployed --feedback "Deployment verified."
```

## Phoenix Voice Roadmap

Current implementation:

- Phoenix reads the live Brain database and dashboard endpoints.
- Phoenix produces operational briefings, machine-level status, next commands, and recommendations.
- The dashboard can speak the briefing with browser speech synthesis.

Next upgrade:

- Use OpenAI Realtime/audio for natural low-latency voice conversation.
- Use OpenAI Agents SDK style orchestration for Phoenix handoffs, guardrails, and traces.
- Keep Postgres as Phoenix memory and the Brain API as Phoenix's tool layer.
- Keep public posting, spending, legal, finance, and account-changing actions behind human approval.

Reference docs:

- Realtime/audio: https://developers.openai.com/api/docs/guides/realtime
- Agents SDK: https://developers.openai.com/api/docs/guides/agents
- Text to speech: https://developers.openai.com/api/docs/guides/text-to-speech
