# PET Scale Architecture

Date: 2026-07-13  
Status: implementation handoff; no release certification implied  
Inputs: `docs/PET_FEATURE_EXECUTION_MATRIX.md`, the uploaded 500-item PET specification, migration `006_pet_release_pipeline.sql`, `ai_ops_center/pet_release.py`, the queue/worker protocol, and the current dashboard motion runtime.

## Decision summary

The platform should treat a PET feature as a versioned product capability, not as a task, animation name, or JSON label. The 500 source definitions are the stable catalog. Revisions, assignments, executions, evidence, telemetry, rubric reviews, and release decisions are separate histories joined by immutable IDs.

The next implementation should be one additive database/API increment: create the exact 500-row feature catalog plus version and state-history tables, seed it idempotently, and expose calculated state totals with an integrity check. That increment establishes the source of truth every later mini-dashboard, animation, assignment, audit, and release workflow needs.

The existing release pipeline is a useful staging layer, but it is not yet the authoritative feature ledger:

- `pet_feature_assignments.feature_ids` and `pet_release_submissions.feature_ids` are JSON arrays, so foreign keys cannot prove that an assigned or submitted ID exists.
- submission evidence, test, audit, rubric, and performance summaries are mutable JSON documents; they cannot independently establish provenance or revisions.
- `pet_performance_samples` supports idempotent sample keys and time indexes, but is not partitioned and has only a callable pruning function, not an enforced retention job.
- release decisions are append-only and idempotent by submission, decision, actor, and evidence hash. This is a strong foundation and should be retained, with an explicit artifact/revision binding.
- the UI advertises 500 governed features and 59 loaded animation names, while the present runtime only chooses a small state-driven subset. Neither number is completion evidence.
- `/stream` rebuilds and broadcasts a broad operations snapshot every five seconds per client. PET scale should use shared snapshots and versioned deltas rather than adding the full ledger and telemetry history to that payload.

## Authoritative model

### Stable catalog and versioned contracts

Use source IDs `PET-01-01` through `PET-20-25`. They never change and are never reused.

```sql
pet_feature_definitions (
  feature_id text primary key,
  domain_no smallint not null check (domain_no between 1 and 20),
  item_no smallint not null check (item_no between 1 and 25),
  source_title text not null,
  source_order smallint not null unique check (source_order between 1 and 500),
  sensitivity text not null,
  default_owner_pet_id text,
  created_at timestamptz not null,
  retired_at timestamptz,
  unique (domain_no, item_no)
)

pet_feature_versions (
  id bigserial primary key,
  feature_id text not null references pet_feature_definitions,
  version integer not null check (version > 0),
  contract jsonb not null,
  acceptance_schema jsonb not null,
  permissions jsonb not null,
  failure_modes jsonb not null,
  content_sha256 char(64) not null,
  created_by text not null,
  created_at timestamptz not null,
  supersedes_version integer,
  unique (feature_id, version),
  unique (feature_id, content_sha256)
)
```

Definitions preserve the user's exact requested titles. Versions contain executable contracts and are append-only. Correcting a contract creates version N+1; it never rewrites evidence collected against version N. Retiring a definition does not delete it or change the invariant total of the original 500.

### State and running totals

Use one current-state row for fast reads and one append-only transition history for audit:

```sql
pet_feature_state_current (
  feature_id text primary key references pet_feature_definitions,
  feature_version integer not null,
  state text not null check (state in ('P','G','O','R')),
  release_id bigint,
  last_verified_at timestamptz,
  verification_expires_at timestamptz,
  row_version bigint not null default 1,
  updated_at timestamptz not null
)

pet_feature_state_events (
  id bigserial primary key,
  feature_id text not null,
  feature_version integer not null,
  from_state text,
  to_state text not null,
  release_id bigint,
  actor text not null,
  reason text not null,
  idempotency_key text not null unique,
  created_at timestamptz not null
)
```

A database function performs a transition under `SELECT ... FOR UPDATE`, verifies the expected `row_version`, inserts the event, and updates current state in one transaction. Only a successful Brain release or canary promotion may produce `O`. Evidence expiry can move a feature to a visibly stale condition without deleting its historical release; the product may either transition back to `P` or retain `O` plus an independent `verification_health='stale'`. The latter is preferred because certification state and freshness answer different questions.

All counts are calculated from `pet_feature_state_current`. The API returns `operational`, `gated`, `planned`, `rejected`, `total`, `expected_total=500`, and `integrity=(total=500)`. Task counts remain a separate namespace.

### Assignments and executions

Replace array-only relationships with join rows while keeping the existing assignment envelope during migration:

- `pet_feature_assignment_items(assignment_id, feature_id, feature_version, ordinal)` with a unique key on assignment and feature.
- `pet_feature_execution_attempts(id, assignment_item_id, task_id, machine_id, agent_id, claim_token_hash, attempt_no, status, started_at, finished_at, result_sha256, idempotency_key)`.
- `pet_feature_execution_events(id, attempt_id, sequence_no, event_type, payload, occurred_at, received_at)` with unique `(attempt_id, sequence_no)`.

An assignment batch is at most five requested features, matching the execution matrix. Task claiming, lease renewal, fenced completion, retry, approval hold, machine pinning, and starvation fallback remain owned by the existing task protocol. PET tables reference tasks; they do not invent a second worker queue.

The worker may submit execution evidence only for its claimed task and target machine. A completed task is necessary but not sufficient for feature promotion. Replayed events return the original result. A later retry has a new attempt number and cannot overwrite the prior attempt.

### Artifacts and evidence

Store artifact metadata in PostgreSQL and binary assets outside the database:

- `pet_artifacts(id, sha256, media_type, byte_size, storage_uri, redaction_state, created_at)`; unique SHA-256 permits content-addressed deduplication.
- `pet_evidence_links(evidence_id, attempt_id, feature_id, feature_version, artifact_id, evidence_type, producer_machine_id, listener_event_id, peer_request_id, test_run_id, created_at)`.
- `pet_test_runs` and `pet_test_cases` preserve runner, environment, pass/fail/skip, duration, and report artifact.
- `pet_rubric_reviews` stores one independent review per reviewer role and rubric version. Dimension scores are rows or validated JSON plus a generated weighted score. The implementation owner cannot be the Quality reviewer.

Every release candidate freezes a manifest with feature/version pairs and artifact hashes. Later artifact replacement requires a new submission. URLs alone are not evidence: the hash, byte size, media type, producer, and verification result are required.

### Animation registry and telemetry

Animations are releaseable assets with semantics, not arbitrary class names:

```text
pet_animation_definitions: animation_id, semantic_state, asset_kind,
manifest_sha256, reduced_motion_animation_id, max_concurrent_instances,
performance_budget, accessibility_contract, version

pet_animation_assignments: pet_id, animation_id, trigger_version,
trigger_predicate, priority, fallback_animation_id, effective release
```

Only allow audited trigger fields such as connectivity freshness, task status, approval state, queue pressure, health thresholds, or a finite completion edge. Trigger evaluation should run in a pure shared function used by main and mini dashboards. Precedence is explicit: security/blocked/offline/stale overrides active work; health warning overrides celebratory state; completion animation is edge-triggered and finite.

Performance samples use a typed envelope: `metric_name`, `value`, `unit`, `aggregation`, `window_ms`, `viewport`, `device_class`, `reduced_motion`, `animation_id/version`, and timestamps. Required release metrics include p50/p95 frame time, long-task count, cumulative layout shift, dropped-frame ratio, memory delta, asset bytes, and concurrent animated PET count. GIFs and videos are referenced as hashed artifacts, lazy loaded, bounded by an asset budget, and paired with static/reduced-motion alternatives.

## Query and index plan

For 500 definitions, exact counts and domain drill-down are inexpensive. Optimize the unbounded histories:

- state current: indexes `(state, updated_at desc)`, `(default owner through definition join or denormalized owner_pet_id, state)`, and `(verification_expires_at) where verification_expires_at is not null`;
- assignment items: `(feature_id, feature_version, assignment_id)` and unique `(assignment_id, feature_id)`;
- attempts: `(machine_id, status, started_at desc)`, `(task_id)`, and partial indexes for active statuses;
- evidence: `(feature_id, feature_version, created_at desc)`, `(attempt_id)`, and unique correlation constraints for listener/peer records where present;
- reviews and decisions: `(submission_id, created_at desc)` and `(feature_id, feature_version, created_at desc)` through release items;
- telemetry: BRIN on `captured_at`, B-tree `(animation_id, captured_at desc)` and `(machine_id, captured_at desc)`.

Do not add broad GIN indexes to every JSON column. Add expression or GIN indexes only after `EXPLAIN (ANALYZE, BUFFERS)` shows a stable query need. Dashboard list endpoints use keyset pagination `(updated_at, id)`, never high-offset pagination.

Partition `pet_performance_samples`, execution events, and high-volume UI telemetry monthly once volume warrants it. Create partitions ahead of time and reject writes only if a safe default partition is unavailable. Keep definitions, current state, assignments, artifacts, reviews, and decisions unpartitioned.

## Retention

Default policy, adjustable through an approved versioned configuration:

| Data | Online retention | Long-term handling |
|---|---:|---|
| raw frame/animation samples | 30 days | hourly aggregates for 13 months |
| execution progress events | 90 days | terminal event and evidence manifest retained |
| listener/speaker operational copies | 90 days after correlation closes | retain referenced evidence IDs and hashes |
| test logs/screenshots | two releases or 180 days | retain release manifest and defect evidence |
| feature definitions/versions/state events | permanent | append-only |
| rubric reviews/release decisions | permanent | append-only |
| customer-sensitive artifacts | policy-specific minimum | deletion tombstone plus non-sensitive hash/audit record |

Pruning runs as a scheduled, observable task in bounded batches, reports deleted rows/bytes to Brain, and never cascades into a release decision. Partition drops require the same audit record as row pruning.

## API, SSE, and cache strategy

Add read APIs before mutation APIs:

- `GET /pet-features/summary` returns totals, integrity, per-domain/per-PET counts, freshness, `catalog_version`, and an ETag.
- `GET /pet-features?domain=&state=&owner=&cursor=&limit=` returns keyset-paginated definitions and current state.
- `GET /pet-features/{id}` returns current version, assignments, releases, and evidence links; histories are separately paginated.
- `GET /pets/{pet_id}/command-view` returns only that PET's assignments, live attempts, blockers, animation state, and release status.
- `POST /pet-features/{id}/transitions` is Brain-only and requires expected row version plus an idempotency key.

The present five-second `/stream` loop computes a full broad snapshot for every connection. Introduce a process-level snapshot service that refreshes shared core data once per interval. Split PET traffic into `/stream/pets`: send an initial summary and then small events containing `event_id`, `catalog_version`, `entity`, `entity_id`, `row_version`, and changed fields. Support `Last-Event-ID`; keep a bounded event replay window and require a summary refetch if the cursor is too old.

Use `Cache-Control: private, no-cache` plus ETag for live summaries so clients revalidate without accepting stale success. Immutable artifact manifests and feature versions may use long-lived cache headers keyed by hash/version. Mini dashboards back off with jitter after SSE errors, use one polling fallback, and label cached data with `as_of` and `stale_after`. They must never optimistically increment completed counts.

## Failure modes and controls

| Failure | Required behavior |
|---|---|
| duplicate catalog seed | unique source ID/order makes seed idempotent; mismatch fails the migration audit |
| concurrent feature promotion | row-version compare-and-swap; one winner, explicit conflict for the other reviewer |
| task finishes after lease expiry | existing fenced completion rejects it; PET attempt stays failed/expired |
| duplicate/reordered laptop events | unique attempt sequence and idempotency key; buffer or reject gaps, never overwrite |
| assignment contains unknown/revised feature | relational foreign key and exact version binding reject it |
| artifact disappears or changes | hash verification fails review; storage URI is not trusted as identity |
| self-approval | reviewer-role and actor separation constraint/policy; release remains held |
| stale/offline PET appears active | semantic precedence forces stale/offline/blocked state and static accessible label |
| SSE disconnect or replay gap | reconnect with cursor; full ETag summary refetch when replay window is exceeded |
| telemetry flood | per-machine rate limit, batch ingestion, payload-size limit, sampling, and partition retention |
| review worker or Brain unavailable | evidence remains submitted/unverified; no automatic promotion |
| partial deployment | channel-specific release record; canary does not change production state |
| bad migration | additive schema, preflight counts, transaction, compatibility reads, and rollback by disabling new writes |

## Safe concurrency boundaries

- One migration owner controls catalog/state schema. Migrations are additive and checksum-audited.
- One protocol owner controls task lease/claim/fencing behavior. Feature executors consume that contract without editing it.
- Feature batches can run concurrently when their feature/version pairs do not overlap. Database uniqueness rejects duplicate active assignment items.
- Main UI, shared mini-dashboard runtime, and each machine-specific page have explicit integrators; animation contributors deliver manifests or isolated modules, not competing edits to shared files.
- Quality and Security review in parallel after an immutable submission exists, but neither edits the submission. A new artifact creates a new submission/review cycle.
- Release promotion is serialized per PET/channel with a PostgreSQL advisory lock or a unique active-release constraint. Different PET canaries may proceed in parallel.
- Telemetry and evidence ingestion can be concurrent and append-only. State transitions and release decisions are the narrow serialized boundaries.

## Rollout and rollback

1. **Shadow catalog:** add definition/version/state tables; seed exactly 500 `P` rows; run integrity and source-hash audits. Existing UI remains unchanged.
2. **Read-only API:** publish summary/detail endpoints and compare counts across database, API, SSE, main dashboard test fixtures, and mini-dashboard fixtures.
3. **Dual relation:** add assignment/submission join rows while continuing to populate existing JSON arrays. Audit equality between both representations. No feature promotion yet.
4. **Evidence pipeline:** add attempts, artifacts, reviews, and release manifests. Replay duplicate/offline/out-of-order cases and run load tests.
5. **Animation canary:** release pure trigger mapping and one PET at a time. Test 320/375/768/1024/1440 widths, reduced motion, stale transitions, reconnects, and the performance budget.
6. **Feature canary:** promote one five-feature batch on one healthy physical laptop only after correlated machine evidence, independent reviews, and Brain approval.
7. **Fleet promotion:** expand by PET and domain while monitoring queue latency, SSE reconnects, database p95, sample ingestion, layout shifts, and false-status defects.

Rollback is channel-specific. Disable new feature writes with a feature flag, restore the previous UI manifest and animation trigger version, stop the canary assignment, and leave append-only evidence/decisions intact. Do not down-migrate by deleting audit tables. If the normalized join path fails, read the dual-written JSON arrays while repairing, then reconcile before resuming promotion.

## Capacity and release SLOs

The definition catalog is fixed at 500 rows. Planning capacity around 100,000 execution attempts/year, 1-5 million execution events/year, and substantially more raw frame samples leaves safe headroom without premature distributed infrastructure. PostgreSQL plus monthly partitions, object storage, bounded SSE replay, and read caching is sufficient at this stage.

Initial service objectives:

- feature summary p95 below 200 ms and detail p95 below 400 ms under the expected dashboard load;
- state-count integrity equals 500 on every read and reconciliation run;
- zero false completion, stale-as-active, cross-machine acknowledgement, or self-approval events;
- SSE event-to-screen p95 below 10 seconds, with no count loss after reconnect;
- animation p95 frame time at or below 16.7 ms on the lowest supported laptop, no sustained animation-caused long tasks, and zero horizontal overflow at required widths;
- 100% release manifests include hashes, passing tests/audits, rollback, independent reviewers, and fresh physical-machine evidence.

## Highest-value next implementation increment

Build migration `007_pet_feature_catalog.sql`, a deterministic seed file, a catalog repository module, and read-only summary/detail APIs with tests. The increment is complete only when:

1. the seed contains 20 domains x 25 items = 500 unique definitions with IDs `PET-01-01` through `PET-20-25`;
2. all 500 initial state rows are `P`, so `O/G/P/R = 0/0/500/0` and integrity is true;
3. rerunning the seed changes zero rows, while altered source text/hash fails loudly;
4. API totals are calculated from the ledger, not constants, tasks, or recent-result limits;
5. unit, migration, duplicate-seed, concurrent-transition, query-plan, and rollback/compatibility tests pass;
6. no UI claim changes until the API contract is accepted by the dashboard integrator.

This increment unlocks safe parallel work: the animation team can bind state semantics to real feature/version IDs, laptop teams can receive relational assignments, Quality/Security can attach independent evidence, and the command-center team can render truthful totals without waiting for all domain implementations.

## Internal validation

- Source structure checked: 20 numbered domains with 25 requested abilities each, yielding 500 definitions.
- Proposed source ID space checked: `20 x 25 = 500`; `PET-01-01` through `PET-20-25` is collision-free under the domain/item uniqueness rule.
- Initial ledger invariant checked: `0 + 0 + 500 + 0 = 500`.
- Existing motion bank checked in `dashboard/app.js`: 59 declared names; declaration is not evidence that every state has a live authoritative trigger.
- Existing release migration checked: four main tables (`pet_feature_assignments`, `pet_release_submissions`, `pet_performance_samples`, `pet_release_decisions`), four status/identity uniqueness controls, append-only release decisions, performance time indexes, and a manual prune function.
- Existing release tests checked: three evidence-gate tests cover incomplete and structurally complete submissions; database constraints, concurrency, performance ingestion, independent review, deployment, and rollback still need integration coverage.
- Cross-reference rule checked: the design retains existing task, listener, speaker, peer, approval, machine, and fenced-worker records rather than duplicating their authority.

