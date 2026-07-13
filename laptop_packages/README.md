# AI Operations Center Laptop Packages

Each package is a self-contained local dashboard and helper bundle for a managed laptop.

Packages:

- `dev-laptop`: Development console, build/test queue, Circuit Mentor pet, Shield monitor.
- `research-laptop`: Research console, source queues, Scout pet, Shield monitor.
- `business-laptop`: Business console, campaign/CRM queue, Ledger pet, Shield monitor.

Install from each laptop after pulling the GitHub repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\laptop_packages\<machine-id>\install.ps1 -BrainHost 100.70.49.32
```

The package opens a local dashboard that talks to the Brain API, polls the speaker feed, publishes heartbeats, and shows a lower-right Mini Phoenix companion. Sensitive commands still require Brain approval.
