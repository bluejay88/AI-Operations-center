# Business Continuity Plan

Use this mode while `business-laptop` is reachable on Tailscale but not yet running as a worker.

## Temporary Work Split

- Brain PC handles coordination, content, digital products, reports, and scorecards.
- Research Laptop handles grants, lead-source research, market intelligence, and opportunity lists.
- Dev Laptop handles website packages, implementation plans, service scaffolds, and production tooling.

## Business Laptop Work Reassignment

The original Business agents remain registered so the Business Laptop can take over later:

- `business-manager`
- `finance-manager`
- `social-media`
- `lead-generation`
- `marketing-agent`

Until then, the system mirrors urgent business-building work to currently available agents:

- `website-builder` on Dev Laptop
- `programmer` on Dev Laptop
- `research-lead` on Research Laptop
- `grant-scout` on Research Laptop
- `content-engine` on Brain PC
- `digital-products` on Brain PC
- `project-coordinator` on Brain PC

## Start The Mode

From the dashboard, click `Distribute Business Work`.

Or call the API:

```powershell
Invoke-RestMethod -Method Post http://localhost:8088/orchestrator/business-continuity
```

## Stop The Mode

Once `business-laptop` is online as a worker:

1. Stop creating new business-continuity batches.
2. Let already-queued continuity tasks finish.
3. Queue fresh business tasks against the Business agents.
4. Run a weekly report and compare which machine handled each category best.
