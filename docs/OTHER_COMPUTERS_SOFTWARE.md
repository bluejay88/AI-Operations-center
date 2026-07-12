# Software For The Other Computers

All computers are already connected to Tailscale, which is the network layer. The next requirement is making each computer able to clone the repo and run its worker container.

## Required On Every Laptop

- Tailscale, signed into the same account.
- Docker Desktop.
- Git for Windows.
- PowerShell.

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

