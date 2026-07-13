# AI Operations Center Laptop Packages

Each package is a self-contained local dashboard and helper bundle for a managed laptop.

Packages:

- `dev-laptop`: Development console, build/test queue, Byte PET, Shield monitor.
- `research-laptop`: Research console, source queues, Nova PET, Shield monitor.
- `business-laptop`: Business console, campaign/CRM queue, Ledger PET, Shield monitor.

Install from each laptop after pulling the GitHub repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\laptop_packages\<machine-id>\install.ps1 -BrainHost 100.70.49.32
```

The package opens a local AI Operations Center Node Console that talks to the Brain API, polls the speaker feed, publishes heartbeats, and shows a project-specific PET companion. Sensitive commands still require Brain approval.

## Laptop Diagnostic Report

Run this from each laptop after pulling GitHub:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\run-laptop-diagnostics.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -BrainUser jayla -StartWorker -CommitReport
```

Change `dev-laptop` to `research-laptop` or `business-laptop` on the other machines. The script writes `diagnostics\<machine-id>\latest.json` and `latest.txt`, publishes the results to the Brain listener/workstation updates, and can commit/push the report so the Brain PC can inspect exact laptop-side errors.
