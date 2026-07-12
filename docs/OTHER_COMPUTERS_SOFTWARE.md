# Software For The Other Computers

All computers are already connected to Tailscale, which is the network layer. The next requirement is making each computer able to clone the repo and run its worker container.

## Required On Every Laptop

- Tailscale, signed into the same account.
- Docker Desktop.
- Git for Windows.
- PowerShell.
- ChatGPT desktop app.

Minimum needed to connect a laptop as a worker: Tailscale + Docker Desktop + Git.
ChatGPT is installed by the onboarding script when Windows allows winget/Microsoft Store installs.

## Strongly Recommended On Every Laptop

- VS Code.
- Chrome.
- Python 3.12.

## Business Laptop

Role: `business-laptop`

Install:

- Docker Desktop.
- Git.
- VS Code.
- Chrome signed into Gmail, Calendar, n8n, Flowise, and business tools.

Later integrations:

- Email and calendar access.
- CRM/accounting tool access.
- Social scheduling accounts.

## Research Laptop

Role: `research-laptop`

Install:

- Docker Desktop.
- Git.
- VS Code.
- Chrome.

Later integrations:

- Browser research profiles.
- Research bookmark folders.
- Data export folder for grants, resale, real estate, and funding.

## Development Laptop

Role: `dev-laptop`

Install:

- Docker Desktop.
- Git.
- VS Code.
- Python 3.12.
- Node.js LTS.
- Netlify CLI after Node is installed.

Later integrations:

- GitHub authentication.
- Netlify authentication.
- Local test runners for Python, React, and API projects.

## First Connection Checklist

If GitHub is not ready yet, create a transfer zip on the brain PC:

```powershell
docker\package-worker-transfer.ps1
```

Copy `exports\ai-operations-center-worker.zip` to the laptop and extract it.

On each laptop, install prerequisites manually or run:

```powershell
docker\install-laptop-prereqs.ps1 -MachineId business-laptop
```

Recommended one-command onboarding:

```powershell
docker\onboard-laptop.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

That command shows `Bleujay Brain is now connected`, checks/installs ChatGPT, joins the worker, and runs a benchmark.

Manual worker configuration:

```powershell
docker\join-worker.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

Run a benchmark from that laptop:

```powershell
docker\run-benchmark.ps1 -MachineId business-laptop -BrainHost 100.70.49.32
```

Then check results on the brain PC:

```powershell
docker compose run --rm ai-ops-api python -m ai_ops_center.cli benchmark-report
```

Change `business-laptop` to `research-laptop` or `dev-laptop` for the other machines.

If the repository is not on GitHub yet, copy the whole `Ai Operations Center` folder to the laptop first, excluding local-only files:

- `.env`
- `flowcheck.py`
- `logs`
- `.docker`
- `__pycache__`

GitHub is still the preferred path because it lets every laptop pull updates.

After GitHub is connected, use:

```powershell
docker\update-worker-from-git.ps1 -MachineId business-laptop -BrainHost 100.70.49.32
```

Change the machine id for the Research and Development laptops.

## Tailscale Names Seen From The Brain PC

The brain PC currently sees:

- `brain-gaming-pc` at `100.70.49.32`
- `desktop-jv56q9p` at `100.112.91.61`
- `desktop-ls24m7v` at `100.71.82.122`
- `laptop-5qgp9kbc` at `100.90.219.88`

Friendly names are okay:

- `Dev Agent` maps to internal worker role `dev-laptop`.
- `Research Agent` maps to internal worker role `research-laptop`.
- `Business Agent` maps to internal worker role `business-laptop`.

Rename each laptop by running this repo command on that actual laptop:

```powershell
docker\rename-this-pc.ps1 -Hostname research-laptop
```

Use `business-laptop` and `dev-laptop` on the other machines. Tailscale's local CLI renames the current device; remote renaming should be done from the Tailscale admin dashboard if you want to rename them all from one place.

Even if the visible Tailscale name is `Research Agent`, run the worker as:

```powershell
docker\join-worker.ps1 -MachineId research-laptop -BrainHost 100.70.49.32
```
