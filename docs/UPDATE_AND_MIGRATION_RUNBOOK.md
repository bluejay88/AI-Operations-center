# Update And Migration Runbook

Use this flow when the Brain PC or laptops need to pull new GitHub updates without collapsing the system.

## GitHub Access

Do not hardcode GitHub passwords or tokens into the repository.

The supported persistent access method is Windows Git Credential Manager:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\setup-github-credential-helper.ps1
git push origin master
```

Sign in as `bluejay88` when Git Credential Manager opens. After that approval, Git stores the credential in Windows Credential Manager for this Windows account and future `git pull` / `git push` operations can run non-interactively.

## Brain PC Update

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\update-brain-from-github.ps1
```

The updater:

- pushes any local Brain commit if credentials are available;
- fetches and fast-forwards from GitHub;
- refuses non-fast-forward pulls;
- compiles critical Python files;
- rebuilds/restarts Docker services;
- applies versioned database migrations;
- reseeds machine/agent registry data;
- runs the release audit;
- restarts the 30-second connectivity monitor;
- writes a timestamped log under `output/`.

## Database Migration Policy

Migrations live in `sql/migrations`.

Each migration is checksum-locked once applied. If an applied migration changes, the updater fails instead of silently corrupting state. New schema changes should be added as a new numbered migration.

Useful commands:

```powershell
docker compose exec -T ai-ops-api python -m ai_ops_center.cli migration-status
docker compose exec -T ai-ops-api python -m ai_ops_center.cli migrate
```

API equivalents:

```powershell
Invoke-RestMethod http://100.70.49.32:8088/migrations
Invoke-RestMethod -Method Post http://100.70.49.32:8088/migrations/apply
```

## Laptop Update

Each laptop can pull the same repository and run its package:

```powershell
git pull origin master
powershell -ExecutionPolicy Bypass -File .\docker\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32
```

Use `research-laptop` or `business-laptop` for those machines.

The Brain dashboard should show laptop Tailscale ping, SSH state, speaker feed, listener events, queued work, completed work, and peer requests after update.
