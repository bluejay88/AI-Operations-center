# PET release pipeline implementation handoff

## Delivered contract

- `POST /pet-releases/assignments` creates an idempotent machine/agent/PET feature assignment and sends it to that laptop's speaker feed.
- `POST /pet-releases/submissions` reserves an idempotent submission, records its Brain listener event, evaluates structural evidence, and either returns targeted evidence feedback or opens a high-risk approval.
- `GET /pet-releases/rubric` publishes the current evidence and deployment policy.
- `POST /pet-releases/submissions/{id}/performance` accepts up to 500 idempotent time-series samples per request and verifies submission ownership by machine ID.
- Existing `POST /approvals/{id}/review` appends PET decisions to an immutable decision ledger. It records outcomes but does not execute deployment.

## Database model and concurrency

Migration `006_pet_release_pipeline.sql` separates assignment state, release submissions, high-volume performance samples, and append-only decisions. Unique `assignment_key`, `submission_key`, and `(submission_id, sample_key)` constraints are the concurrency boundary; clients should generate stable keys from their local job/attempt identity and safely retry on network timeouts. The submission row is reserved before listener/approval side effects, preventing two concurrent retries from creating duplicate approval requests.

Rows left in `processing` indicate an interrupted workflow and must be reconciled by a future recovery steward; they must not be treated as passed. Assignment and submission indexes support machine/status and task/approval queues. Performance samples have both submission/time lookup and a BRIN time index for large append-heavy datasets.

## Retention and telemetry

Call `select prune_pet_performance_samples(now() - interval '90 days')` from an approved scheduled maintenance workflow. The function deliberately has no implicit schedule, so operators choose retention to meet evidence and compliance needs. Keep aggregated release evidence in `pet_release_submissions` even when raw samples expire. Future ingestion should batch samples and use `(submission_id, sample_key)` idempotency.

## Verification and release policy

`evidence_complete` means required fields, nonzero test/audit counts, zero reported failures, artifact references, performance measurements, and rollback instructions are present. It does not prove the evidence is genuine. Every new submission starts `submitted_unverified` with `release_authorized=false`. Brain/human reviewers must reproduce relevant tests, inspect artifacts, confirm reduced-motion/accessibility behavior, and attach review evidence.

`approved` is authorization evidence only. A release system must separately perform a staged/canary deployment, verify health and rollback, then record `deployed` with immutable deployment evidence. Never infer deployment from a successful submission or approval.

## Follow-on work

1. Add authenticated machine identity so callers cannot spoof `machine_id` or `agent_id`.
2. Add a recovery steward for stale `processing` submissions and an outbox if listener/approval side effects require transactional delivery guarantees.
3. Add batch telemetry ingestion with payload and rate limits.
4. Add assignment/result query endpoints with pagination and scoped authorization.
5. Add a release executor that consumes only explicit approvals and emits canary/rollback evidence; keep it separate from this intake path.
