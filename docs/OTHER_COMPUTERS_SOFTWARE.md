# Software For The Other Computers

All computers are already connected to Tailscale, which is the network layer. The next requirement is making each computer able to clone the repo and run its worker container.

## Required On Every Laptop

- Tailscale, signed into the same account.
- Docker Desktop.
- Git for Windows.
- PowerShell.

Minimum needed to connect a laptop as a worker: Tailscale + Docker Desktop + Git.

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

On each laptop:

```powershell
git clone YOUR_REPO_URL
cd "Ai Operations Center"
docker\configure-worker-env.ps1 -MachineId business-laptop -BrainHost 100.70.49.32
docker\check-brain.ps1 -BrainHost 100.70.49.32
docker\worker-bootstrap.ps1 -MachineId business-laptop
```

Change `business-laptop` to `research-laptop` or `dev-laptop` for the other machines.

If the repository is not on GitHub yet, copy the whole `Ai Operations Center` folder to the laptop first, excluding local-only files:

- `.env`
- `flowcheck.py`
- `logs`
- `.docker`
- `__pycache__`

GitHub is still the preferred path because it lets every laptop pull updates.

## Tailscale Names Seen From The Brain PC

The brain PC currently sees:

- `brain-gaming-pc` at `100.70.49.32`
- `desktop-jv56q9p` at `100.112.91.61`
- `desktop-ls24m7v` at `100.71.82.122`
- `laptop-5qgp9kbc` at `100.90.219.88`

Rename each laptop by running this repo command on that actual laptop:

```powershell
docker\rename-this-pc.ps1 -Hostname business-laptop
```

Use `research-laptop` and `dev-laptop` on the other two machines. Tailscale's local CLI renames the current device; remote renaming should be done from the Tailscale admin dashboard if you want to rename them all from one place.
