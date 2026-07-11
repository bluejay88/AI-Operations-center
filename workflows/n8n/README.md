# n8n Workflow Templates

Primary n8n workspace: `https://aioperation.app.n8n.cloud`

These workflow templates are intentionally simple starting points. Import them into n8n cloud, then update credentials, schedule times, and webhook URLs.

## Templates

- `morning-report.json`: Daily morning report trigger.
- `hourly-report.json`: Hourly status report trigger.
- `weekly-revenue-review.json`: Weekly revenue and backlog review trigger.

## API Endpoints Used

- `GET http://brain-gaming-pc:8088/reports/morning`
- `GET http://brain-gaming-pc:8088/reports/hourly`
- `GET http://brain-gaming-pc:8088/reports/weekly`
- `POST http://brain-gaming-pc:8088/orchestrator/daily-priorities`

If Tailscale MagicDNS is not enabled, replace `brain-gaming-pc` with the Gaming PC Tailscale IP.

