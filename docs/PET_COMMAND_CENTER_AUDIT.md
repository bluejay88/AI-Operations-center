# PET Command Center Release Audit

Date: 2026-07-13  
Scope: Main AI Operations Center, Dev PET (Byte), Research PET (Nova), Business PET (Ledger), queue execution, lifetime task accounting, live connectivity, and deployment.

## Current release decision

**CORE DEPLOYED / FLEET VALIDATION PARTIAL.** The API, Brain worker, PostgreSQL, dashboards, migration ledger, lifetime accounting, queue lease/fencing protocol, and read-only release gates are operational. All three laptops answer fresh Tailscale probes, but the Business and Research workers have not consumed their pinned diagnostic requests. Business accepts TCP/22 but rejects the Brain public key; Research blocks TCP/22. Those physical-laptop gates remain open and are not represented as passed.

## Current evidence

- Final pre-starvation build test baseline: `37 passed` with four FastAPI lifecycle deprecation warnings.
- Added queue-starvation assertions pass inside the rebuilt image: portable stale work moves, the generation cap prevents ping-pong, and full fallback targets are skipped.
- Docker services: API and Brain worker recreated from the final image; PostgreSQL healthy.
- Migrations: `001` through `004` applied, zero pending, all checksums match. Migration `002` accepts only its known historical checksum; migration `004` enforces leased and fenced completion.
- Live protocol audit: expired completion rejected, wrong-session completion rejected, valid fenced completion accepted, and the audit transaction rolled back.
- Lifetime accounting at final release audit: 3,341 completed tasks; `/tasks`, readiness, NOC, and per-machine totals reconcile while the recent list remains independently limited.
- Fresh network pulse: Dev 26 ms, Research 3 ms, Business 19 ms over Tailscale; all three targets reachable.
- Worker activity gate: only 1 of 3 registered laptop workers was active during the final audit.
- Business task `3794` and peer request `4`: queued/requested with no machine claim or response. Fresh direct SSH result: `Permission denied (publickey)`.
- Research task `3795` and peer request `5`: queued/requested with no machine claim or response. Fresh TCP/22 result: blocked.
- Brain execution probe task `3792`: completed once under a fenced claim with real hostname, platform, Python, and timestamp evidence.
- Approval-hold probe task `3793`: remained queued with zero attempts, proving held work is not auto-claimed.

## Stage gates

| Stage | Rubric | Evidence | Result |
|---|---|---|---|
| 1. Task accounting | Lifetime database aggregate; independent recent list; global count equals machine sum | 3,341 completed; accounting audit passed; `/tasks`, readiness, and NOC parity passed | PASS |
| 2. Queue protocol | Claims are leased, completion is fenced, expired/wrong-session completion is rejected | Migration `004` plus rolled-back PostgreSQL protocol audit | PASS |
| 3. Queue fallback | Eligible portable work cannot remain indefinitely on a heartbeat-only non-claiming source | 60-second starvation fallback, capacity-aware target selection, bounded generation cap; pinned and approval-held work excluded | PASS |
| 4. Connectivity truth | Tailscale, worker heartbeat, TCP/22, and authenticated SSH remain separate signals | 3/3 Tailscale reachable; 1/3 laptop workers active; Business key rejected; Research port blocked | PASS WITH FLEET WARNINGS |
| 5. Main command center | Preserve controls, authoritative totals, PET attributes/capabilities, and responsive containment | Main page HTTP 200 with self-only CSP; PET/release/status surfaces use authoritative summaries | PASS |
| 6. Mini dashboards | Correct machine identity, responsive PET layout, controls, feeds, and task visibility | Dev, Research, and Business mini dashboards return HTTP 200 with the expected safe machine identity | PASS |
| 7. Automated tests | Queue, accounting, connectivity, security, API, UI contracts, and routing pass | 37-test baseline passed; final queue-starvation image assertions passed | PASS |
| 8. Deployment | Rebuilt services start and expose application health without migration drift | Final API/worker image deployed; health and migration endpoints pass | PASS |
| 9. Business physical round trip | Business claims task, acknowledges speaker request, returns local evidence, and responds to peer request | Task `3794` unclaimed; peer `4` requested; SSH key rejected | FAIL / LAPTOP ACTION REQUIRED |
| 10. Research recovery | Research publishes diagnostic artifact and classifies/fixes SSH blocker | Task `3795` unclaimed; peer `5` requested; TCP/22 blocked | FAIL / LAPTOP ACTION REQUIRED |

## Corrective implementation completed

1. Completed counts now come from lifetime database aggregates and reconcile across the main dashboard, mini dashboards, readiness, NOC, and SSE payloads.
2. Queue claims use claim tokens, leases, renewal heartbeats, retry backoff, dead-letter limits, and database-enforced fenced completion.
3. Portable queued tasks are rebalanced from unavailable, overloaded, or non-claiming machines. Approval-held, pinned, no-failover, and local-resource tasks remain protected.
4. The worker performs real connectivity or model execution and publishes a correlated completion listener event; canned completion output and pre-execution delay were removed.
5. Speaker acknowledgements require the target machine identity. Receipt events no longer create new speaker messages, eliminating recursive `Received: Received:` loops.
6. Peer responses require the addressed responder and can correlate to their task through `peer_request_id` metadata.
7. The laptop diagnostic analyzer is read-only by default, acknowledges only its own diagnostic requests after running checks, reports blocked outcomes as non-success, and classifies SSH service/port/firewall/key blockers without exposing private keys.
8. PET layouts retain existing controls while improving capability, attribute, workload, connectivity, and release-assurance presentation with responsive containment.

## Required laptop actions

- Business laptop: authorize the approved Brain public key for the `jayla` account, start the current worker/listener loop, then allow task `3794` and peer request `4` to complete naturally.
- Research laptop: run the provided diagnostic command locally with the required administrator permissions for OpenSSH/firewall setup, publish `diagnostics/research-laptop/latest.json`, start the current worker, then complete task `3795` and peer request `5`.
- Do not mark either laptop gate passed until its machine-originated task result, speaker acknowledgement, fresh heartbeat, diagnostic artifact, and peer response are all correlated.

## Repeatable audits

- `docker/audit-live-release.ps1` - read-only API, accounting, connectivity, CSP, and mini-dashboard release audit.
- `docker/audit_queue_protocol.py` - transactional PostgreSQL lease/fencing audit that rolls back its temporary task.
- `docker/run-laptop-diagnostics.ps1` - machine-local pulse and SSH blocker analyzer.

Historical browser screenshots in `output/playwright/` are layout evidence only; live API and machine-originated evidence take precedence for release status.
