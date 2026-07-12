# Git Distribution Runbook

This repo should become the source of truth for the brain PC and all worker laptops.

## Goal

- Brain PC pushes code, policy, Docker, agent, and config updates.
- Laptops pull the latest approved version.
- Each laptop restarts its worker with the newest instructions.
- Benchmarks and heartbeats confirm that the update deployed.

## Step 1: Create The GitHub Repo

Create a private GitHub repository named:

```text
ai-operations-center
```

Recommended visibility: private.

Do not commit local secrets. These are already ignored:

- `.env`
- `flowcheck.py`
- `logs/`
- `exports/`
- `.docker/*` except `.docker/config.json`

## Step 2: Connect The Brain PC Repo

From the brain PC repository folder, run this with your actual GitHub URL:

```powershell
docker\configure-git-remote.ps1 -RemoteUrl https://github.com/YOUR-USER/ai-operations-center.git
```

Then push:

```powershell
docker\push-brain-updates.ps1
```

If Git asks you to sign in, complete the browser/device login.

This repo currently uses the `master` branch. That is okay; the laptops will pull from `master` by default.

## Step 3: Clone On Each Laptop

On each laptop, choose a folder such as:

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/YOUR-USER/ai-operations-center.git
cd ai-operations-center
```

Then run the matching onboarding command.

Development laptop:

```powershell
powershell -ExecutionPolicy Bypass -File docker\onboard-laptop.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

Research laptop:

```powershell
powershell -ExecutionPolicy Bypass -File docker\onboard-laptop.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

Business laptop:

```powershell
powershell -ExecutionPolicy Bypass -File docker\onboard-laptop.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

## Step 4: Deploy Future Updates

After the brain PC commits and pushes a change, run this on each laptop:

Development laptop:

```powershell
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32
```

Research laptop:

```powershell
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId research-laptop -BrainHost 100.70.49.32
```

Business laptop:

```powershell
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId business-laptop -BrainHost 100.70.49.32
```

## Step 5: Verify From The Brain PC

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli status
docker compose run --rm ai-ops-api python -m ai_ops_center.cli benchmark-report
```

## Remote Deployment Later

To make the brain PC push commands directly to laptops, enable one remote command layer on each laptop:

- Tailscale SSH or Windows OpenSSH Server.
- PowerShell Remoting / WinRM restricted to Tailscale.
- A remote desktop tool.

Once that exists, the brain PC can run each laptop's `docker\update-worker-from-git.ps1` remotely.
