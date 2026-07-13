# LLM Mesh and Laptop Recovery Bundle

## Brain LLM Mesh

The Brain now has a policy-driven LLM mesh for local and non-local development work.

Endpoints:

- `GET /llm-mesh/status`
- `POST /llm-mesh/route`
- `POST /llm-mesh/query`
- `GET /team-chat`
- `GET /team-chat/digest`
- `POST /team-chat/post`
- `POST /team-chat/brain-decision`
- `GET /laptop-agents/{machine_id}/contract`
- `GET /laptop-agents/{machine_id}/prompt`
- `GET /codex/pipeline`
- `POST /codex/pipeline`

Docker service:

```powershell
docker compose up -d ai-ops-llm-router
```

Optional local model stack:

```powershell
docker compose --profile ai-tools up -d ollama open-webui
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

Routing policies live in `config/llm_mesh.yaml`.

The mesh supports:

- edge/offline chat and Q&A through Ollama
- coding/debugging through local coder models first, then cloud fallback
- fast routing/summaries through Groq when configured
- stronger coding/reasoning through OpenAI when configured
- long review/writing through Claude when configured
- research/alternate critique through Gemini when configured

Guardrails:

- no spending, public deployment, credential changes, email sending, legal/financial commitments, or destructive filesystem actions without approval
- sensitive prompts prefer local routes
- failures are audited and redacted
- model tasks must produce evidence, not fake completions

## Laptop Recovery Bundle

Each laptop can pull the newest bundle from GitHub and run one recovery command.

Run from the repo root on the laptop:

```powershell
cd "$env:USERPROFILE\Desktop\AI-Operations-center"
git pull --ff-only origin master
powershell -ExecutionPolicy Bypass -File .\docker\laptop-recovery-bundle.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -UpdateCode -StartWorker -QueueProbe
```

Research:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\laptop-recovery-bundle.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -UpdateCode -StartWorker -QueueProbe
```

Business:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\laptop-recovery-bundle.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -UpdateCode -StartWorker -QueueProbe
```

To repair inbound SSH, run Administrator PowerShell and add `-RepairSsh`:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\laptop-recovery-bundle.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -UpdateCode -RepairSsh -StartWorker -InstallStartupTask -QueueProbe
```

The bundle performs:

- Brain API health check
- machine-specific AI node contract download
- local prompt export for the laptop's OpenAI/Codex/helper agents
- optional Git update
- optional Tailscale-only OpenSSH repair
- Brain public key install
- diagnostics report
- speaker feed read/ack for diagnostic messages
- listener event publish
- mini dashboard package install
- worker/listener/speaker loop startup
- workload probe creation
- optional startup scheduled task
- team room announcement that the laptop contract was downloaded

The team room is the backend chatlog for Brain, laptops, agents, models, and workflows. The Brain can ingest `/team-chat/digest`, then post CEO-level decisions or questions through `/team-chat/brain-decision`; targeted laptops receive those directions through their speaker feed and the message remains auditable in PostgreSQL.

## Codex-To-Laptop Pipeline

Codex, the Brain PC, or any registered laptop can pipe work into the whole system through:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\pipe-codex-task.ps1 `
  -Title "Build the first website offer dashboard section" `
  -Body "Create a development plan, research notes, business copy, QA checklist, and completion evidence. Do not deploy or contact customers without approval." `
  -TargetMachines brain-gaming-pc,dev-laptop,research-laptop `
  -DeliveryMethods dashboard,github `
  -CreatePeerRequests
```

That call creates:

- dashboard-visible operator requests
- queue tasks for the selected laptop agents
- speaker messages for each selected laptop
- a team-room thread under `/team-chat`
- optional peer requests between laptops so they can ask each other for research, QA, assets, or handoff help
- listener/audit events so the Brain can ingest progress and decide next actions

Laptops send work back through:

- `POST /team-chat/post` for team-room updates, questions, model results, blockers, decisions, and completion summaries
- `POST /listener/events` for progress logs, errors, recommendations, and task completion evidence
- `POST /collaboration/peer-requests` when one laptop needs help from another
- `POST /collaboration/peer-requests/{request_id}/respond` when returning peer work
- `POST /codex/pipeline` when a laptop or local agent needs to create new Brain-visible routed work

Security posture:

- SSH is restricted to Tailscale `100.64.0.0/10`
- password auth is disabled unless explicitly enabled in the lower-level SSH setup script
- private keys are never copied or reported
- diagnostics verify authorized key files and can verify the expected Brain public-key fingerprint
