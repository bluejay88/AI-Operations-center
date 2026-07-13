# PET Feature Execution Matrix

Date: 2026-07-13  
Source specification: `500 PET Features and Abilities for Each Laptop`  
Scope: Phoenix/Brain, Byte/Development, Nova/Research, Prism/Business, Shield/Security, and the three laptop mini dashboards.

## Audit decision

The uploaded specification contains exactly 20 capability domains with 25 requested abilities in each domain (500 total). The repository has meaningful PET, queue, communications, approval, telemetry, audit, and animation foundations, but it does **not** yet contain feature-by-feature acceptance evidence for all 500 abilities.

The existing `ai_ops_center/enterprise_features.py` catalog is a separate 20-by-25 implementation-work template. It generates generic actions such as “Define policy” and “Build data model”; it does not preserve the 500 requested ability names. Likewise, the dashboard statement “500 features governed” is a roadmap label, not proof that 500 abilities work.

For that reason, the release-certified starting ledger is deliberately conservative:

| State | Certified count | Meaning |
|---|---:|---|
| Operational (`O`) | 0 | No requested ability is counted until its own acceptance record and machine-originated evidence pass. |
| Approval-gated (`G`) | 0 | Approval infrastructure exists, but no requested ability is counted here until both the executor and denial/approval paths pass. |
| Planned (`P`) | 500 | Every requested ability has an owner and completion contract below; existing substrates reduce work but do not waive acceptance. |
| Rejected/unsafe (`R`) | 0 | No requested outcome is rejected outright. Unauthorized variants of sensitive abilities must be rejected by policy. |
| **Total** | **500** | Must always equal `O + G + P + R`. |

This ledger prevents “task created,” “model produced text,” “animation name exists,” or “button rendered” from being misreported as “feature completed.”

## State rules and running totals

A feature may move from `P` to `O` only when all of the following are correlated by `feature_id`:

1. an implementation artifact exists in the repository or approved external system;
2. deterministic unit or contract tests pass;
3. the assigned physical machine executes a success-path probe and returns a non-empty result;
4. the result reaches Brain through a `task_completed` listener event and, when delegated, a fulfilled peer response;
5. the quality/rubric reviewer records requirements, security, accessibility, failure-path, and rollback results;
6. Brain records a release decision after checking the artifact, tests, audit log, and current machine connectivity.

A sensitive feature moves from `P` to `G` only after its executor exists and tests prove that an unapproved request is held or rejected, an approved request can run once, and the action is auditable and reversible. Approval alone does not make the feature operational.

The authoritative ledger should use one immutable row per requested item:

```text
feature_id, domain_no, item_no, title, owner_machine_id, owner_agent_id,
state, acceptance_version, task_id, listener_event_id, peer_request_id,
approval_request_id, test_artifact, audit_artifact, reviewed_by,
released_at, last_verified_at
```

The Brain readout must calculate, never hand-edit:

```text
completed_total = count(state = 'O')
approval_gated_total = count(state = 'G')
planned_total = count(state = 'P')
rejected_total = count(state = 'R')
integrity = completed_total + approval_gated_total + planned_total + rejected_total = 500
```

Task completion totals and PET-feature completion totals are different metrics. A feature can require many tasks, and completing 500 backlog tasks does not prove 500 features.

## Per-mini-dashboard ownership

| Surface / PET | Machine ID | Primary feature ownership | Assigned agents | Brain feedback package |
|---|---|---|---|---|
| Main Command Center / Phoenix | `brain-gaming-pc` | Brain communication, finance oversight, advanced autonomy, release decisions | `orchestrator`, `project-coordinator`, `finance-manager` | aggregate ledger, queue/accounting audit, release rubric, approval decisions |
| Development mini dashboard / Byte | `dev-laptop` | desktop automation, files, websites, infrastructure, device maintenance | `programmer`, `website-builder`, `database-optimizer` | build artifact, tests, browser/layout evidence, rollback plan, listener pulse |
| Research mini dashboard / Nova | `research-laptop` | research and knowledge work, source verification | `research-lead`, `grant-scout` | source manifest, dates, reliability rubric, cited report, peer response |
| Business mini dashboard / Prism | `business-laptop` | conversation, documents, spreadsheets, design, media, customer, sales, fulfillment, marketing | `business-manager`, `content-engine`, `social-media`, `lead-generation`, `digital-products` | deliverable manifest, QA score, approval need, business metric, listener pulse |
| Main security surface / Shield | `security-monitor` on Brain | security/privacy gates and continuous policy review | `security-monitor`, `policy-steward-ai`, `access-review-ai` | threat/policy findings, deny-path evidence, approvals, incident and rollback record |
| Independent quality lane | Brain-visible; not a production owner | all-domain review; must not approve its own work | `rubric-auditor`, Quality PET | independent rubric score, defect list, retest result, release recommendation |

Quality and Security retain stop authority. They must be able to return `needs_changes`, request human review, or block a release without the Executive PET overriding the evidence.

## 500-item domain matrix

Each row below maps all 25 source items in that numbered section. Initial release state is `P` for all 25 until item-level evidence is entered. The “existing substrate” column is implementation evidence that can accelerate work; it is not counted as certified completion.

| # | Requested domain (items) | Owner dashboard / PET | Accountable agent(s) | Existing substrate, not yet feature certification | Sensitive or unsafe variants that must be gated/rejected | Initial O/G/P/R |
|---:|---|---|---|---|---|---:|
| 1 | Core Identity and Personality (1–25) | Main + every mini / all PETs | `project-coordinator`; each role owner | machine registry and role-specific Phoenix/Byte/Nova/Prism/Shield profiles in `dashboard/app.js`; package identity in `laptop_packages/*` | impersonation, owner-bypass, unauthorized-user recognition changes | 0/0/25/0 |
| 2 | Brain Communication (26–50) | Main + every mini / Phoenix | `orchestrator` | leased/fenced task claims, queue steward, speaker/listener bus, peer requests, workload and health reporting | unsigned/spoofed instructions, replay, wrong-target acknowledgement, unsafe remote cancel/transfer | 0/0/25/0 |
| 3 | Local Conversation Abilities (51–75) | Business / Prism | `business-manager`, `content-engine` | model-task intake and work-product responses; browser speech support for Brain briefing | always-on microphone, voice identity claims, recording or reading private content without consent | 0/0/25/0 |
| 4 | Desktop Assistance (76–100) | Development / Byte | `programmer` | remote-operation request policy and mini-dashboard request surface | launching/closing apps, screen capture/recording, window control, restarts, remote takeover without explicit scope | 0/0/25/0 |
| 5 | File and Folder Management (101–125) | Development / Byte | `programmer`, `database-optimizer` | remote file operations are recognized as sensitive; export/import and checksum concepts exist in the platform | deletion, quarantine, movement, archive restore, retention changes, access outside allowed roots | 0/0/25/0 |
| 6 | Document Creation (126–150) | Business / Prism | `content-engine`, `business-manager` | generic model work products and deliverable planning | contracts, invoices, receipts, certificates, or branded customer delivery without template and human review | 0/0/25/0 |
| 7 | Spreadsheet and Data Abilities (151–175) | Business + Brain / Prism + Phoenix | `business-manager`, `finance-manager`, `database-optimizer` | KPI, financial, database, and dashboard data structures | financial calculations or exports treated as authoritative without formula audit and source reconciliation | 0/0/25/0 |
| 8 | Research and Knowledge Work (176–200) | Research / Nova | `research-lead`, `grant-scout` | research tasks, model routing, structured work products, Brain handoff | regulated advice, uncited claims, prohibited scraping, monitoring outside approved targets | 0/0/25/0 |
| 9 | Creative Design Abilities (201–225) | Business / Prism | `content-engine`, `digital-products`, `social-media` | PET visual system and generic creative work planning | trademark/logo assertions, copyrighted asset misuse, public/customer delivery without approval | 0/0/25/0 |
| 10 | Video and Audio Abilities (226–250) | Business / Prism | `content-engine`, `social-media` | browser speech briefing and model-generated scripts/outlines | voice cloning, likeness use, background-music licensing, recording or publication without consent | 0/0/25/0 |
| 11 | Website Creation and Management (251–275) | Development / Byte | `website-builder`, `programmer` | dashboard web application, build/test/deploy request types, health endpoints | payment connections, analytics identifiers, production deployment, rollback, customer portals, destructive updates | 0/0/25/0 |
| 12 | Customer Service (276–300) | Business / Prism | `business-manager`, `customer-service` | business workflow/approval matrices and model work products | identity verification, account reset, refunds, customer messages, order disclosure | 0/0/25/0 |
| 13 | Sales and Lead Management (301–325) | Business / Prism | `lead-generation`, `business-manager` | business pipeline, lead, product, and KPI schemas/plans | outbound messages, quotes/offers, affiliate/commission actions, customer profiling without policy | 0/0/25/0 |
| 14 | Order Fulfillment (326–350) | Business / Prism | `content-engine`, `digital-products`, `business-manager` | fulfillment pipeline planning, task ownership, approval matrix | payment-status claims, customer delivery, customer-data handling, revision closure without verification | 0/0/25/0 |
| 15 | Finance and Business Monitoring (351–375) | Main / Phoenix | `finance-manager`, `rubric-auditor` | financial KPI and revenue-model structures; approval policies | banking, refunds, tax/accounting claims, transaction mutation, payment reminders without Jayla approval | 0/0/25/0 |
| 16 | Marketing Automation (376–400) | Business / Prism | `social-media`, `marketing-agent`, `content-engine` | campaign/content planning and business KPIs | public posts, email sends, paid campaign changes, spend, unsupported public claims | 0/0/25/0 |
| 17 | Security and Privacy (401–425) | Main / Shield | `security-monitor`, `policy-steward-ai`, `access-review-ai` | approval processor, remote-operation policy, security guardian audit, fenced claims, audit tables | credential changes, lockdown, quarantine, firewall/security setting changes, surveillance, destructive containment | 0/0/25/0 |
| 18 | Quality Assurance and Checks (426–450) | Independent quality lane / Quality PET | `rubric-auditor` | test suite, accounting/protocol/release audits, approval scoring, task/listener evidence | self-approval, bypassing failed gates, leaking customer data in test artifacts | 0/0/25/0 |
| 19 | Device Health and Maintenance (451–475) | Development + each mini / Byte + local PET | `programmer`, local machine worker | heartbeats, telemetry fields, network/SSH diagnostics, connectivity/readiness surfaces | OS updates, restarts, cleanup, log deletion, archive moves without maintenance approval and rollback | 0/0/25/0 |
| 20 | Advanced Autonomy and Intelligence (476–500) | Main / Phoenix | `orchestrator`, `rubric-auditor` | priority queue, starvation fallback, model mesh, peer collaboration, completion/accounting audits | autonomous policy changes, skill installation, unreviewed learning, unsafe degraded operation, shutdown | 0/0/25/0 |
|  | **Running total** |  |  |  |  | **0/0/500/0** |

## Acceptance batches and completion criteria

The 25 items in each domain should be delivered in five auditable batches of five. Batch completion never implies domain completion; a domain is complete only when all 25 item records are `O` or intentionally `G` with a release-approved reason.

| Batch | Required output to Brain | Pass criteria |
|---|---|---|
| A — contract | five exact source titles, IDs, owner, inputs/outputs, permissions, failure modes | no generic renamed substitutes; every title traceable to the uploaded source |
| B — implementation | code/config/artifacts and a manifest with hashes | implementation is real, scoped, and runnable on the assigned machine |
| C — tests | unit, integration, denial, timeout, offline, accessibility/layout, and rollback tests as applicable | tests pass from a clean environment; failures do not produce false completion |
| D — physical PET proof | task claim/result, listener event, peer response, heartbeat, and artifact path | evidence originates from the target machine; IDs correlate; lease and identity checks pass |
| E — independent release | Quality score, Security decision, Brain rubric and release/hold record | no self-approval; high-impact action has explicit Jayla approval; rollback is usable |

## Brain feedback and rubric artifact contract

Every batch submission should produce one JSON manifest plus linked files:

```json
{
  "feature_ids": ["PET-02-01"],
  "owner_machine_id": "brain-gaming-pc",
  "owner_agent_id": "orchestrator",
  "task_ids": [],
  "listener_event_ids": [],
  "peer_request_ids": [],
  "approval_request_ids": [],
  "artifacts": [{"path": "...", "sha256": "..."}],
  "tests": {"passed": 0, "failed": 0, "report": "..."},
  "rubric": {
    "requirements": 0,
    "security": 0,
    "reliability": 0,
    "usability_accessibility": 0,
    "auditability": 0,
    "rollback": 0
  },
  "decision": "hold",
  "reviewed_by": [],
  "observed_at": "ISO-8601"
}
```

Recommended gate: every rubric dimension at least 80, weighted total at least 90, zero critical security defects, zero false-completion paths, and fresh physical-machine evidence. Brain may decide `release`, `canary`, `hold`, or `reject`; only `release`/successful `canary` may update a requested feature to `O`.

## PET animation delivery lane

Animation work is a visual/status subsystem, not proof of the 500 business abilities. The current dashboard declares 59 named states and contains corresponding CSS keyframes, plus workload, connection, on-roll, heavy-work, signal, stream, and flare effects. Only a subset is selected by live state logic in `chooseAnimation`; therefore “59 names loaded” must not be treated as “59 live state integrations passed.”

| Animation owner | Assignment | Evidence required |
|---|---|---|
| Prism / `content-engine` | define expressive motion concepts, poses, visual language, and per-PET personality variants | storyboard/motion tokens, reduced-motion alternative, contrast and readability review |
| Byte / `programmer` | implement state mapping, transitions, responsive containment, performance budget, and no-overlap layout | automated DOM/state tests, screenshots at phone/tablet/desktop widths, frame/performance trace |
| Nova / `research-lead` | review motion accessibility, cognitive-load, status-symbol clarity, and common dashboard patterns | cited research brief and recommendations sent to Brain |
| Shield / `security-monitor` | verify animations do not imply success when the underlying status is stale, blocked, or unverified | semantic truth table and false-status audit |
| Quality / `rubric-auditor` | run visual regression, reduced-motion, keyboard, screen-reader-label, and data-truth audits | independent report with defects, retest IDs, and release recommendation |
| Phoenix / `orchestrator` | correlate animation state to authoritative readiness/task/telemetry signals and decide release | canary/release record, rollback reference, before/after metrics |

Animation release gates:

- every rendered state has an authoritative triggering signal and an explicit fallback;
- stale/offline/blocked never renders as active success;
- `prefers-reduced-motion` produces a calm, understandable equivalent;
- no text overlap or horizontal overflow at 320, 375, 768, 1024, and 1440 CSS pixels;
- PET cards preserve accessible names and status text without relying on color or motion alone;
- animation work stays within a documented frame/rendering budget;
- screenshots, browser console results, and automated assertions are returned to Brain before deployment.

## Release sequence

1. Replace or supplement the generic enterprise catalog with immutable source-aligned IDs `PET-01-01` through `PET-20-25`; do not silently rename the requested abilities.
2. Seed work in five-item batches per domain, with the owner mapping above and no duplicate active work.
3. Require each laptop to publish machine-originated progress and final artifacts to Brain; queued or unclaimed work remains incomplete.
4. Quality and Security independently audit each batch and send results through listener/peer/approval records.
5. Brain chooses hold, canary, release, or reject based on evidence and current connectivity, not backlog counts.
6. Update the running ledger transactionally only after the release decision; retain prior evidence and status history.
7. Deploy to the relevant mini dashboard first, observe a canary window, then promote to the main Command Center. Roll back on status mismatch, layout regression, security failure, or physical-worker silence.

## Team handoff and safe concurrency

The work can run in parallel by artifact boundary, but not by editing the same source-of-truth record or shared UI file. A batch lead owns integration for each five-feature batch.

| Lane | May run concurrently with | Exclusive boundary / handoff rule |
|---|---|---|
| Source-ledger and database contract | animation concepts, research, test-plan drafting | one migration owner; additive migrations only; no concurrent edits to the same schema/migration file; ledger IDs are immutable after seeding |
| Brain API and accounting | mini-dashboard CSS concepts, physical diagnostics | one API integrator for task/feature counters; API must calculate totals from ledger rows, not browser state or recent-task pages |
| Queue/worker execution | UI layout and animation implementation | one protocol owner for claim/lease/fencing changes; executors may be added in separate modules but merge through the protocol owner |
| Main Command Center UI | mini-dashboard implementation if shared files are untouched | `dashboard/app.js`, `dashboard/styles.css`, and `dashboard/index.html` each have one active integrator; others submit patches or design notes |
| Shared mini-dashboard runtime | main UI and machine-specific HTML | `laptop_packages/shared/*` has one integrator; machine-specific pages may proceed independently only when the shared contract is frozen |
| Byte, Nova, Prism machine-specific acceptance | each other physical laptop | each laptop owns its own artifacts and may not manufacture another laptop’s heartbeat, acknowledgement, or peer response |
| Quality review | all implementation lanes after a reviewable checkpoint | reviewer must not author the artifact under review; defect fixes return to the implementation owner and require retest |
| Security review | design, implementation, and QA | Shield may block/hold but does not silently rewrite production work; policy changes require a versioned approval record |
| Deployment | documentation and next-batch planning | one release captain; deploy only immutable tested image/artifact hashes; no code changes during the observation window |

Cross-lane dependencies:

```text
source-aligned ledger
  -> feature API and transactional totals
  -> main/mini dashboard readouts
  -> batch task creation and assigned executor
  -> machine-originated result and Brain feedback
  -> Quality + Security decisions
  -> canary deployment
  -> ledger promotion and main release
```

No downstream lane may simulate an upstream gate. In particular, UI work cannot create feature completion, Brain cannot manufacture a laptop-originated pulse, and an approval record cannot substitute for a functioning executor.

## Performance, stability, and database implications

| Area | Risk introduced by the 500-feature program | Required guardrail and evidence |
|---|---|---|
| Database | 500 features can create thousands of task, event, test, approval, and history rows; ad-hoc counting can become slow or inconsistent | normalized immutable feature table plus append-only status history; indexed `feature_id`, `state`, owner, and verification timestamps; transactionally updated status; query-plan evidence |
| Running totals | double counting from retries, recent-page limits, duplicated seeds, or feature/task confusion | uniqueness on source `feature_id`; totals derived from feature state; invariant `O+G+P+R=500`; reconciliation audit shown in API/SSE/main/minis |
| Queue | bulk seeding can starve operational/diagnostic work or overload a reachable machine | five-item batches, bounded per-machine workload, existing starvation fallback, approval/pin protections, retry/backoff/dead-letter metrics |
| Brain bus | every task can emit messages and listener events, causing feed growth or receipt loops | correlation IDs, idempotency/dedupe, pagination, target ownership, no receipt-to-speaker echo, event-rate and backlog checks |
| Worker stability | long creative/research tasks may outlive leases or falsely complete with prose instead of artifacts | lease renewal, fenced completion, typed executor contract, artifact/hash validation, timeout/cancellation tests, non-empty result is necessary but not sufficient |
| Main UI | rendering all 500 rows and many animated PETs can increase layout cost and hide live operations | aggregate first; paginate/virtualize item detail; throttle live renders; preserve authoritative totals; browser performance and console evidence |
| Mini dashboards | shared polling from three laptops can multiply API traffic; offline/stale state can look active | SSE or bounded polling with backoff/jitter; last-success timestamp; cached read-only fallback labeled stale; no optimistic completion |
| Animation | 59 simultaneous transforms/effects can consume CPU/GPU, trigger motion sensitivity, or overlap text | animate compositor-friendly properties, limit concurrent effects, reduced-motion mode, containment, frame trace, responsive screenshot suite |
| Evidence storage | screenshots, media, and reports can bloat Git/database or expose sensitive data | manifest metadata in DB; artifacts in approved storage; hashes and retention policy; log redaction; no secrets/private keys/customer data |
| Release | partial laptop connectivity can yield a green core while fleet behavior is unverified | separate core, per-laptop, and full-fleet gates; stable observation interval; current heartbeat/SSH/worker evidence; explicit partial/block state |

Minimum stability soak for a batch should cover multiple heartbeat, queue-steward, polling/SSE, and lease-renewal cycles. A UI-only animation batch should still be observed with live state changes, reconnects, stale transitions, reduced motion, and no console errors. The observation duration belongs in the artifact instead of being inferred from a single screenshot.

## Prioritized next waves

### Wave 0 — truth and release safety (P0)

1. Create the exact 500-row source ledger with immutable IDs and status history; import all source titles verbatim after fixing encoding artifacts.
2. Add a feature-accounting audit and expose the four state totals plus integrity result through API, SSE, main dashboard, and each mini dashboard.
3. Remove or relabel any UI wording that can be read as “500 implemented”; show certified, gated, planned, blocked, and last-verified counts.
4. Keep Business and Research feature acceptance blocked until their workers return correlated physical-machine evidence.
5. Define typed feature result manifests, artifact hashing, idempotency, and independent Quality/Security decisions.

### Wave 1 — PET status and animation truth (P0/P1)

1. Map every selectable animation to an authoritative state predicate and add tests for offline, stale, queued, running, blocked, failed, completed, approval-held, and recovery transitions.
2. Add reduced-motion behavior and make status understandable without movement or color.
3. Run no-overlap and no-horizontal-scroll checks at the required widths on Phoenix, Byte, Nova, Prism, and Shield cards.
4. Limit concurrent high-energy effects and measure render/frame behavior with live updates.
5. Return a single animation audit manifest to Brain with screenshots, console output, accessibility results, state truth table, and rollback reference.

### Wave 2 — mini-dashboard command surfaces (P1)

1. Give each mini dashboard a source-aligned assigned-feature view with batch, state, blocker, approval, evidence, and last-verified fields.
2. Add an “acknowledged / claimed / running / evidence submitted / reviewed” timeline without treating acknowledgement as completion.
3. Add local diagnostic and artifact-submission affordances that target only the page’s machine identity.
4. Use bounded reconnect/backoff and show API reachability, worker heartbeat, Tailscale, TCP/22, and authenticated SSH as separate signals.
5. Run machine-specific browser, API-contract, identity-spoof, and stale-data tests before promotion.

### Wave 3 — main Command Center orchestration (P1)

1. Add portfolio drill-down from 20 domains to five-item batches and individual features without rendering all detail at once.
2. Add Brain release queues for Quality-pass/Security-pass/approval-needed/canary-ready, with immutable evidence links.
3. Display capacity and starvation data beside assignments so new work goes only to healthy claiming workers.
4. Add performance and evidence-retention dashboards; alert on count mismatch, duplicate IDs, stale verification, bus backlog, or repeated retries.
5. Add canary/promotion/rollback controls that require tested artifact hashes and retain the prior release.

### Wave 4 — domain implementations (P2, incremental)

Implement the 20 domains in five-item batches, starting with Brain Communication, Security/Privacy, QA, Device Health, and Advanced Autonomy because they are prerequisites for safely releasing customer, finance, file, desktop, and publishing capabilities. High-impact business actions remain held until the supporting identity, approval, audit, rollback, and physical-worker controls have passed.

## Immediate blockers

- There is no source-aligned 500-row feature ledger yet; the generic 500-task catalog is not a substitute.
- Business and Research physical workers must consume and answer their pinned diagnostic work before their machine-originated acceptance evidence can pass.
- PET capability labels in the UI are currently profile summaries, not item-level certification.
- Approval gates and worker executors must both be present before an ability can be counted as `G` or `O`.
- No feature should be promoted solely because an LLM returned prose, a backlog task completed, or a CSS animation exists.
