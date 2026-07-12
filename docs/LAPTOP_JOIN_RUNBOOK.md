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

Fast path: run the full onboarding command on the laptop. This shows the desktop message, installs/checks the laptop prerequisites, installs/checks ChatGPT, joins the worker pool, and records a benchmark.

Business laptop:

```powershell
docker\onboard-laptop.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

Research laptop:

```powershell
docker\onboard-laptop.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

Development laptop:

```powershell
docker\onboard-laptop.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

If you only want the visible connection popup on a laptop:

```powershell
docker\show-connected-message.ps1
```

Manual path: first rename that laptop in Tailscale:

```powershell
docker\rename-this-pc.ps1 -Hostname business-laptop
```

Use `research-laptop` or `dev-laptop` on the other machines.

Then join the worker:

Business laptop:

```powershell
docker\join-worker.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

Research laptop:

```powershell
docker\join-worker.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

If the device is already named `Research Agent` in Tailscale, that is fine. The worker role should still be `research-laptop`.

Development laptop:

```powershell
docker\join-worker.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

## Verify From The Gaming PC

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli status
docker compose run --rm ai-ops-api python -m ai_ops_center.cli report hourly
```

Or watch status from the brain PC:

```powershell
docker\watch-workers.ps1
```

Each running laptop should show as online within five minutes.

## If A Laptop Does Not Show Online

1. Confirm Docker Desktop is running on the laptop.
2. Confirm Tailscale is connected.
3. Run `docker\check-brain.ps1 -BrainHost brain-gaming-pc`.
4. If MagicDNS fails, use the Gaming PC Tailscale IP instead of `brain-gaming-pc`.
5. Restart the worker command.

## Remote Control Notes

Tailscale proves the laptops can reach the brain PC, but it does not automatically grant remote PowerShell control. To run onboarding remotely from the brain PC, enable one remote command channel on each laptop:

- Tailscale SSH or Windows OpenSSH Server.
- PowerShell Remoting / WinRM over the Tailscale network.
- A remote desktop tool where you can run the onboarding command locally.

Until one of those is enabled, run `docker\onboard-laptop.ps1` directly on each laptop.
