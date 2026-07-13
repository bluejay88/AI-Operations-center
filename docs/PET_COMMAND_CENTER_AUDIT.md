# PET Command Center Release Audit

Date: 2026-07-13  
Scope: Main AI Operations Center, Dev PET (Byte), Research PET (Nova), Business PET (Ledger), lifetime task accounting, live connectivity, and deployment.

## Release decision

**PASS WITH FLEET WARNINGS** — core application, task accounting, and live network reachability gates pass. Only one of three laptop workers currently has a fresh heartbeat, and direct Brain-to-laptop SSH remains pending until administrator setup is completed on each physical laptop. The UI reports both conditions separately instead of treating reachability, worker activity, and direct control as equivalent.

## Stage gates

| Stage | Rubric | Evidence | Result |
|---|---|---|---|
| 1. Task accounting | Completed count is a lifetime database aggregate, independent of the recent-task list; global count equals the sum of machine counts | `/tasks?limit=3` returned 3 rows while retaining the full completed total; `completed_equals_machine_sum=true` | PASS |
| 2. Real-time parity | REST, readiness, NOC, and SSE expose the same completed total | Final deployed audit reconciled 2,817 completed tasks across `/tasks`, readiness, NOC, and per-machine totals while the recent list remained limited to three rows | PASS |
| 3. Connectivity truth | Stale reports cannot count as effectively online; browser presence cannot impersonate a worker heartbeat; reachability, worker activity, and direct control are separate | The scheduled monitor verifies three reachable targets. Business has a fresh worker heartbeat; Dev and Research are reachable with stale workers. Direct SSH currently warns `0/3` | PASS + 2 WARN |
| 4. Main command center | Preserve controls, show authoritative totals, expose PET attributes and capability status, avoid desktop/mobile horizontal overflow | 23 baseline controls and 53 DOM targets preserved; Playwright at 1440x1000 and 390x844 reported no overflow, five PET cards, contained PET text, and 39 visible mobile buttons | PASS |
| 5. Mini dashboards | Each node keeps identity, controls, feeds, task table, PET functions, and responsive containment | Byte/Nova/Ledger pages each retain 22 stable IDs, 6 controls, task table, three feeds, CSP-safe identity configuration, shared responsive breakpoints, and eight browser-audit hooks | PASS |
| 6. Security/governance | Privileged browser/file actions remain approval-gated; inline configuration complies with CSP | Brain-governed controls remain separate from operational functions; inline config was removed after CSP browser audit and replaced with external-script-readable data attributes | PASS |
| 7. Automated tests | Python contracts, configuration, accounting, freshness, availability, presence isolation, and invariants pass | Rebuilt Python 3.12 container: `14 passed` | PASS |
| 8. Static quality | JavaScript parses, Python compiles, and patch has no whitespace errors | `node --check` for both bundles, `compileall`, and `git diff --check` passed | PASS |
| 9. Deployment | Rebuilt services start, recover automatically, and expose application health | PostgreSQL, API, and worker use restart policies; all three containers became healthy; the strict live audit passes core gates and separately warns on stale physical workers and unavailable direct SSH | PASS + WARN |

## Defects found by rendered auditing

1. The main SSE stream delivered an integrations object while the renderer expected an array. The stream normalization now extracts `providers`, and a fresh browser session reports zero console errors.
2. Mini dashboards used inline identity scripts that the production Content Security Policy blocked. Identity is now supplied through per-page `data-*` attributes and consumed by the shared external script.
3. The old completed widgets counted only the limited recent task list. All completed widgets now prefer the lifetime task summary, with readiness/factory/recent-list fallbacks.
4. The workforce test and copy hard-coded 18 agents while configuration had expanded to 30. The test now enforces a minimum workforce and unique IDs; UI copy no longer publishes a stale fixed count.
5. Mini dashboards posted a fabricated health score and their browser-presence request refreshed authoritative worker heartbeat tables. Browser presence is now stored only as a labeled observation; worker status and PET state derive from readiness and real task totals. A SQL-recording regression test proves the presence path cannot touch `machine_status_current` or `machine_heartbeats`.
6. Release readiness was only implicit across several panels. The main dashboard now includes a live Release Assurance rail for accounting, lifetime totals, connectivity-contract freshness, readiness parity, and PET capability coverage.
7. Freshness invariants could pass vacuously with zero online targets. The connection contract now has a separate availability rubric, and both the dashboard and release script require it for a connectivity pass.
8. A non-elevated Tailscale CLI permission error was incorrectly published as a remote laptop outage. The scanner now falls back to raw ICMP, labels the probe method, reports unreachable results as unknown, and runs every 30 seconds.

## PET specification coverage

- Main dashboard: five live PET profiles, attributes, operational capabilities, governed/planned capabilities, feature lanes, workload, health, connectivity, task totals, and motion states.
- Mini dashboards: unique identities and traits for Byte, Nova, and Ledger; 12 role-specific operational functions per PET; live task/health state; Brain messages; approvals; remote operations; speech; refresh; and permission-gated assistance requests.
- The source specification's 20 domains / 500 features remain the governed capability roadmap. Features requiring credentials, external services, financial authority, customer data, public sending, remote control, or destructive access remain approval-gated and are not represented as autonomously available.

## Audit artifacts

- `output/playwright/main-desktop.png`
- `output/playwright/main-mobile.png`
- `output/playwright/mini-dev-desktop.png`
- `docker/audit-live-release.ps1` (repeatable, read-only, 9-gate production audit)
