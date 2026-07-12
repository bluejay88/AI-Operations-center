# Laptop Join Runbook

Use this after all machines are connected to Tailscale.

## Machine Names

- Gaming PC: `brain-gaming-pc`
- Laptop A: `business-laptop`
- Laptop B: `research-laptop`
- Laptop C: `dev-laptop`

Current discovered Gaming PC Tailscale IP: `100.70.49.32`.

If Tailscale MagicDNS does not resolve `brain-gaming-pc`, use `100.70.49.32` as `BrainHost`.

## On The Gaming PC

Rename this Tailscale device if needed:

```powershell
docker\rename-this-pc.ps1 -Hostname brain-gaming-pc
```

Allow Tailscale workers to reach the brain API and Postgres:

```powershell
docker\configure-brain-firewall.ps1
```

Install the brain prerequisites if Docker Desktop is not installed:

```powershell
docker\install-brain-prereqs.ps1
```

Approve the Administrator prompt. Restart Windows if the installer or WSL requests it.
After restart, open Docker Desktop once and let it finish its first-run setup.

Then run:

```powershell
docker\resume-brain-after-reboot.ps1
```

If Docker Desktop reports that it cannot start, run:

```powershell
docker\recover-brain-core.ps1
```

If that script tells you Docker still cannot start, open Docker Desktop > Troubleshoot. First try Restart Docker Desktop. If it still fails, use Clean / Purge data or Reset to factory defaults. This Docker install is fresh, so that only removes Docker's local images, containers, volumes, and broken cache.

Start the brain stack:

```powershell
docker\brain-bootstrap.ps1
```

Check local health:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli status
```

## On Each Laptop

Clone or copy the repository, then configure that laptop.

If GitHub is not ready yet, create `exports\ai-operations-center-worker.zip` from the brain PC:

```powershell
docker\package-worker-transfer.ps1
```

Copy and extract that zip on the laptop.

On each laptop, first rename that laptop in Tailscale:

```powershell
docker\rename-this-pc.ps1 -Hostname business-laptop
```

Use `research-laptop` or `dev-laptop` on the other machines.

Business laptop:

```powershell
docker\configure-worker-env.ps1 -MachineId business-laptop -BrainHost 100.70.49.32
docker\check-brain.ps1 -BrainHost 100.70.49.32
docker\worker-bootstrap.ps1 -MachineId business-laptop
```

Research laptop:

```powershell
docker\configure-worker-env.ps1 -MachineId research-laptop -BrainHost 100.70.49.32
docker\check-brain.ps1 -BrainHost 100.70.49.32
docker\worker-bootstrap.ps1 -MachineId research-laptop
```

Development laptop:

```powershell
docker\configure-worker-env.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32
docker\check-brain.ps1 -BrainHost 100.70.49.32
docker\worker-bootstrap.ps1 -MachineId dev-laptop
```

## Verify From The Gaming PC

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli status
docker compose run --rm ai-ops-api python -m ai_ops_center.cli report hourly
```

Each running laptop should show as online within five minutes.

## If A Laptop Does Not Show Online

1. Confirm Docker Desktop is running on the laptop.
2. Confirm Tailscale is connected.
3. Run `docker\check-brain.ps1 -BrainHost brain-gaming-pc`.
4. If MagicDNS fails, use the Gaming PC Tailscale IP instead of `brain-gaming-pc`.
5. Restart the worker command.
