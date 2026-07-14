# Update And Migration Runbook

Use this flow when the Brain PC or laptops need to pull new GitHub updates without collapsing the system.

## GitHub Access

Do not hardcode GitHub passwords or tokens into the repository.

The supported persistent access method is Windows Git Credential Manager:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\setup-github-credential-helper.ps1
git push origin master
```

Sign in as `Bluejay88` when Git Credential Manager opens. The setup stores only the username hint and configures Git Credential Manager. After approval, Git Credential Manager stores the OAuth credential in Windows Credential Manager for this Windows account, so future GitHub operations do not repeatedly prompt. Never put a password or token in Git configuration, scripts, remotes, or `.env`.

## Brain PC Update

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\update-brain-from-github.ps1
```

The updater:

- does not push local commits by default;
- fetches and fast-forwards from GitHub;
- refuses non-fast-forward pulls;
- compiles critical Python files;
- rebuilds/restarts Docker services;
- applies versioned database migrations;
- reseeds machine/agent registry data;
- runs the release audit;
- restarts the 30-second connectivity monitor;
- writes a timestamped log under `output/`.

After Brain/human review, an approved publish must carry its review identifier:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\update-brain-from-github.ps1 -PushApproved -BrainApprovalId REVIEW-123
```

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
$approved = "<full-or-abbreviated-approved-commit-sha>"
powershell -ExecutionPolicy Bypass -File .\docker\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -ApprovedCommit $approved -BrainApprovalId REVIEW-123
```

Use `research-laptop` or `business-laptop` for those machines.

The worker updater refuses dirty worktrees, non-fast-forward history, and a branch head that differs from the approved commit. It never resets, force-pushes, or embeds credentials.

The Brain dashboard should show laptop Tailscale ping, SSH state, speaker feed, listener events, queued work, completed work, and peer requests after update.
