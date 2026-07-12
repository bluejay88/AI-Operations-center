# Network Setup

## Recommended Stack

- Docker Desktop on all machines.
- Tailscale on all machines.
- Git on all machines.
- VS Code on all machines.
- Ollama on the Gaming PC first; optional on laptops later.
- Open WebUI on the Gaming PC.
- Flowise cloud or local Flowise on the Gaming PC for visual AI chains.
- n8n cloud at `https://aioperation.app.n8n.cloud` for primary automations.
- Optional local n8n on the Gaming PC for development and fallback.
- PostgreSQL on the Gaming PC.
- Netlify CLI on the Development Laptop and Gaming PC.

## Tailscale Plan

1. Install Tailscale on the Gaming PC and all three laptops.
2. Sign in with the same account.
3. Name devices:
   - `brain-gaming-pc`
   - `business-laptop`
   - `research-laptop`
   - `dev-laptop`
   You can do this from this repo with `docker/rename-this-pc.ps1 -Hostname brain-gaming-pc`, changing the hostname for each device.
4. Use the Gaming PC Tailscale IP or MagicDNS hostname as the central API and database host.
5. Update each laptop `.env`:

```text
DATABASE_URL=postgresql://aiops:aiops@brain-gaming-pc:5432/aiops
WORKER_MACHINE_ID=business-laptop
```

Change `WORKER_MACHINE_ID` for each laptop.

## Startup Order

1. Start Docker on the Gaming PC.
2. Run `docker/brain-bootstrap.ps1`.
3. Confirm `http://localhost:8088/health` returns `{"status":"ok"}`.
4. On each laptop, run `docker/configure-worker-env.ps1 -MachineId business-laptop -BrainHost 100.70.49.32`.
5. Confirm the laptop can reach the brain with `docker/check-brain.ps1 -BrainHost 100.70.49.32`.
6. Start each laptop worker with `docker/worker-bootstrap.ps1 -MachineId business-laptop`.
7. Check heartbeats with `python -m ai_ops_center.cli status`.

See `docs/LAPTOP_JOIN_RUNBOOK.md` for the full machine-by-machine checklist.

## n8n Cloud

Use `https://aioperation.app.n8n.cloud` as the primary automation workspace. The Docker Compose n8n service remains useful for testing workflows locally before importing them into the cloud account.

## Flowise

Flowise should own reusable AI chains. Add your Flowise cloud URL to `.env` as `FLOWISE_URL`. If you want the local fallback, run the Docker Compose `flowise` service and open `http://localhost:3001`.

Use n8n to schedule a workflow, then call either Flowise directly or the AI Operations API endpoint `/integrations/flowise/predict`.

## GitHub Repository

Create a private GitHub repository named `ai-operations-center`, then from this folder:

```powershell
git init
git add .
git commit -m "Create AI Operations Center foundation"
git branch -M main
git remote add origin https://github.com/YOUR-USER/ai-operations-center.git
git push -u origin main
```

After the repository exists, each laptop can clone it and run the worker profile.
