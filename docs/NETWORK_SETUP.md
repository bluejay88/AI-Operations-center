# Network Setup

## Recommended Stack

- Docker Desktop on all machines.
- Tailscale on all machines.
- Git on all machines.
- VS Code on all machines.
- Ollama on the Gaming PC first; optional on laptops later.
- Open WebUI on the Gaming PC.
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
4. Start each laptop worker with `docker/worker-bootstrap.ps1 -MachineId business-laptop`.
5. Check heartbeats in the morning or hourly report.

## n8n Cloud

Use `https://aioperation.app.n8n.cloud` as the primary automation workspace. The Docker Compose n8n service remains useful for testing workflows locally before importing them into the cloud account.

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
