# AI Operations Center Security Baseline

This system controls multiple laptops, revenue workflows, research, code, and future business automation. Treat it as a private operations platform.

## Network Boundary

- Keep the brain API on the private Tailscale network.
- Do not port-forward `8088`, `5432`, `9418`, n8n, Flowise, Open WebUI, or Ollama to the public internet.
- Firewall inbound access to Tailscale addresses only wherever possible.
- Prefer worker-to-brain API calls over direct laptop-to-Postgres access as the system matures.

## Secrets

- Never commit `.env`, `flowcheck.py`, API keys, tokens, cookies, database dumps, or browser profile data.
- Rotate any key that was pasted into a file later committed to GitHub.
- Use read-only scopes for research/finance integrations whenever possible.

## Human Approval

Keep human approval required for:

- Sending emails, social posts, or customer messages.
- Spending money, creating invoices, moving funds, or changing billing settings.
- Legal, tax, LLC, contract, or compliance work.
- Deleting files, rewriting history, or removing business records.

## Dashboard And API

- Production API docs should be disabled unless protected by Tailscale or another access control layer.
- Browser dashboard content must escape task text and other user-supplied strings.
- Dashboard/API responses should use structured JSON for status and task state; avoid parsing Markdown for control logic.
- Security headers are enabled by the FastAPI app, including CSP, frame blocking, no-sniff, and strict referrer policy.

## Laptop Workers

- Each laptop should run only its assigned worker role unless explicitly promoted.
- Workers should heartbeat every 5-15 seconds into `machine_status_current`.
- Connectivity scans should record only reachability metadata, not credentials or private files.
- Workers should claim tasks through leases before doing production work.
- Lost/stale laptops should have leases expired and tasks returned to the queue.

## Git And Deployment

- GitHub is the source of truth for code and policy.
- Keep the repository private.
- Laptops should pull updates from GitHub and redeploy with the provided scripts.
- Do not store machine-specific secrets in Git; use each laptop's local `.env`.
