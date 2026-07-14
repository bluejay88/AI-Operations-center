# n8n Workflow Templates

Primary n8n workspace: `https://aioperation.app.n8n.cloud`

These workflow templates are intentionally simple starting points. Import them into n8n cloud, then update credentials, schedule times, and webhook URLs.

## Templates

- `morning-report.json`: Daily morning report trigger.
- `hourly-report.json`: Hourly status report trigger.
- `weekly-revenue-review.json`: Weekly revenue and backlog review trigger.
- `connectivity-diagnostic-response.json`: Five-minute external diagnostic loop that publishes deduplicated markers, sends governed speaker queries to affected nodes, and records an audit event.

## Connectivity Diagnostic Workflow

Run this workflow on the Brain-hosted n8n service (the `automation-tools` Docker Compose profile) or on an n8n runner that can reach the Brain through Tailscale. Set `BRAIN_API_URL` to the private Brain API, for example `http://brain-gaming-pc:8088`. Do not expose the unauthenticated Brain API directly to the public internet.

The workflow is inactive after import. Review its URLs and network access, then activate it. It can collect evidence, publish listener events, and send allowlisted diagnostic queries. It cannot run arbitrary shell commands, change credentials, replace SSH host keys, force-reset Git, or deploy an unreviewed commit.

An update remains a two-part governed handoff:

1. Brain/human review produces a review ID and exact approved commit SHA.
2. The target runs `docker\\update-worker-from-git.ps1` with `-ApprovedCommit` and `-BrainApprovalId`.

## API Endpoints Used

- `GET http://brain-gaming-pc:8088/reports/morning`
- `GET http://brain-gaming-pc:8088/reports/hourly`
- `GET http://brain-gaming-pc:8088/reports/weekly`
- `POST http://brain-gaming-pc:8088/orchestrator/daily-priorities`
- `GET http://brain-gaming-pc:8088/connections/diagnostics`
- `POST http://brain-gaming-pc:8088/connections/diagnostics/publish`
- `POST http://brain-gaming-pc:8088/connections/diagnostics/query`
- `POST http://brain-gaming-pc:8088/listener/events`

If Tailscale MagicDNS is not enabled, replace `brain-gaming-pc` with the Gaming PC Tailscale IP.
