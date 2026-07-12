# Hybrid Business Coverage

Until the dedicated Business Laptop is worker-online, the Brain PC, Dev Laptop, and Research Laptop share Business AI responsibilities.

## Current Hybrid Assignment

- Brain PC: coordination, admin planning, finance summaries, content drafts, reports, Phoenix briefings, final approval.
- Research Laptop: lead generation, grant research, business opportunities, market intelligence, resale/arbitrage discovery, source validation.
- Dev Laptop: website offers, landing pages, service package scaffolds, client delivery systems, QA, deployments, automation implementation.

## Transition Trigger

Business Laptop is considered ready when:

- Tailscale is online.
- Worker heartbeat is current.
- Benchmark is recorded.
- It completes at least one low-risk business task.
- Speaker feed and listener event tests pass.

## Auto-Update Rule

When Business Laptop becomes ready:

1. Brain marks it as worker-online.
2. Phoenix announces the transition.
3. New business tasks route to business-laptop agents.
4. Queued fallback business tasks are re-evaluated and moved if safe.
5. Running tasks stay with current owners unless the Brain approves transfer.
6. Reports and dashboard summaries update the hybrid coverage status.

## Task Sorting Rules

- Leads and grants go to Research while Business is offline.
- Website packages and deployment prep go to Dev.
- Social, content, and outreach drafts go to Brain content-engine while Business is offline.
- Finance and admin planning go to Brain project-coordinator while Business is offline.
- No external sending, spending, filing, or publishing happens without approval.

