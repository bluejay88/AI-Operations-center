# Independent security/runtime review — PET machine capabilities

Date: 2026-07-13 23:25 CDT
Scope: `pet_machine_capabilities.py`, migrations 015/016, API routes, mini-dashboard request surface, worker/runtime wiring, and Docker secret handling.

## Worker-integration addendum

The worker-runtime absence identified as `REL-MC-01` has been remediated in source: the worker now consumes `pet_capability_signed_execution`, constructs the target executor, keeps every capability flag and handler disabled by default, checks for an existing receipt before invocation, records a signed machine receipt/listener event, and only then acknowledges the addressed speaker message. Its strict characterization assertion now passes. This closes only the worker-listener gap; the security HOLD remains because the key-separation, nonce/replay, receipt binding, SSRF, dispatch-idempotency, executor-policy, and API-authority findings are unresolved. Migration 016 must remain pending and executors must remain disabled.

Decision: **HOLD — do not apply migration 016 or deploy/enable executors yet**

## Ground truth

- Migration 015 is applied. Migration 016 is pending and its checksum is `dc694d53236dd6122994e4d0d26dc0d80663aa15f00a2f137df7c460a6670765`.
- Per-machine dispatch/receipt keys are not configured in the current `.env`; dispatch and receipt ingestion therefore fail closed.
- No worker listener imports or invokes `MachineCapabilityExecutor`, and no browser, music, or model handler is instantiated. The lane is not physically operational.
- Focused implementation plus independent review suite: **31 passed / 13 strict expected-failed**, with four FastAPI lifespan warnings.
- Requests, dispatch responses, and status responses retain `success_claimed: false`. This review did not change any feature ledger state.

## Positive controls verified

1. Dispatch checks the authoritative approval row for browser/music before signing (`ai_ops_center/pet_machine_capabilities.py:159-164`).
2. HMAC comparison is constant-time, the executor verifies its exact machine target, and the signed executor name must match the capability (`pet_machine_capabilities.py:201-210`).
3. All handlers are disabled by default and return a held receipt when absent (`pet_machine_capabilities.py:193-213`).
4. Request payloads reject file/javascript schemes, direct non-public IP literals, credentials, fragments, arbitrary music paths, unknown fields, and invalid PET/machine pairs.
5. Migration 015 makes request rows append-only and never gives them a completed status. API/UI request acceptance is not represented as execution success.

## Release blockers

### SEC-MC-01 — Remediated in source / still requires provisioning evidence

Location: `ai_ops_center/pet_machine_capabilities.py:197-204`, `226-239`, `258-262`; `docker-compose.yml:79-121`.

The current source uses per-machine directional dispatch and receipt key environment variables with `key_id` binding. Executor enablement still requires out-of-band secret provisioning evidence, rotation/revocation policy, and proof that keys are not distributed through broad bundles or unrelated services.

Required fix: use per-machine, direction-separated keys or Brain dispatch signatures plus per-machine receipt signatures; bind a `key_id`, support rotation/revocation, and provision only the minimum key to each target worker. Do not distribute it through `.env.example` or the general laptop bundle.

### SEC-MC-02 — High — signed execution is indefinitely replayable

Location: `pet_machine_capabilities.py:166-180`, `201-218`, `273-277`.

Envelopes have no nonce, issued/expiry time, dispatch hash, or target-side replay store. Replaying one valid envelope invokes an enabled handler repeatedly. Repeated API dispatch also creates a new speaker message before the database's `ON CONFLICT DO NOTHING`, then reports `dispatched` even when no new dispatch row was stored.

Required fix: reserve the dispatch transactionally before publishing, include a random nonce and bounded expiry, consume it atomically on the target, and return the existing immutable dispatch on retries without another speaker side effect.

### SEC-MC-03 — High — receipts are not bound to a dispatch or capability

Location: `pet_machine_capabilities.py:226-239`, `280-286`; `sql/migrations/016_pet_machine_capability_dispatch.sql:8-18`.

Receipt ingestion checks request ID, machine, and PET, but not capability type, approval ID/status, dispatch existence, signed-envelope hash, or contract version. A correctly signed `completed` receipt can be recorded before dispatch or with a different capability. The SQL uniqueness key includes the surrogate `id`, so it never deduplicates a repeated request receipt.

Required fix: require one authoritative dispatch; bind receipt to request, capability, target, approval, dispatch-envelope SHA-256 and nonce; enforce a state transition policy; use an effective uniqueness/idempotency key; append contradictory later reports without treating them as completion.

### SEC-MC-04 — High — URL validation is bypassable and not repeated at execution

Location: `pet_machine_capabilities.py:329-361`, `211-216`.

Alternate IPv4 forms such as `2130706433`, `0x7f000001`, and `0177.0.0.1` pass validation but commonly resolve to loopback. Hostnames are not resolved and pinned, redirects are not evaluated, and an empty domain allowlist permits any hostname. The target executor does not revalidate even a signed browser payload before invoking its handler, so key compromise becomes an SSRF/private-network navigation primitive.

Required fix: require a nonempty normalized domain allowlist; reject ambiguous numeric hosts; resolve all A/AAAA records at execution and reject non-global answers; revalidate every redirect hop; defend against DNS rebinding; repeat validation on the target immediately before navigation.

### REL-MC-01 — High — no worker/runtime execution path exists

Location: `ai_ops_center/worker.py` (no capability message handling), `pet_machine_capabilities.py:190-223`.

The executor is only a class used in unit tests. No worker consumes `pet_capability_signed_execution`, no receipt is posted from a physical machine, and no enabled handler exists. Applying migration 016 or exposing controls would not make the feature operational.

Required fix: implement a target-only listener that verifies and consumes the signed dispatch, keeps every executor disabled by default, calls explicit local handlers only, posts the signed receipt, and demonstrates a physical round trip with separate machine evidence.

### SEC-MC-05 — Medium — target executor trusts signed policy fields and omits contract validation

Location: `pet_machine_capabilities.py:201-216`.

The target checks signature, machine, authority flag, and executor name, but it does not require the exact contract version, enforce approval for browser/music, validate approval identity, or validate payload schema. A shared-key holder can sign `approval_status=pending` or unsafe payloads and still reach an enabled handler.

Required fix: make target authorization policy independent of caller fields; require the exact version and required fields; validate remote approval evidence and payload locally; reject extra fields and malformed canonical JSON.

### SEC-MC-06 — Medium — API authority and actor identity are caller asserted

Location: `ai_ops_center/api.py:1202-1223`; `pet_machine_capabilities.py:176`.

The new POST routes have no route-level authentication dependency, and `actor` is accepted from the request body. Approval state prevents unapproved browser/music dispatch, but an untrusted network caller can create approval spam, replay approved dispatches, or claim any dispatch actor. Receipt submission relies only on possession of the shared key.

Required fix: authenticate the operator/worker at the API boundary, authorize per machine/action, derive actor from authentication, rate-limit request creation, and separate worker receipt credentials from operator dispatch credentials.

## Required pre-deploy evidence

1. All 13 strict characterization failures become passing safeguards without weakening their assertions.
2. Migration 016 is superseded by a new immutable migration if it has been applied anywhere; otherwise correct it before first application. Prove request/dispatch/receipt concurrency and rollback in PostgreSQL.
3. Run valid, tampered, wrong-target, wrong-capability, expired, replay, duplicate dispatch, duplicate receipt, missing approval, revoked key, database outage, and redirect/DNS-rebinding probes.
4. Verify Docker/container inspection exposes no signing key to unrelated services, logs, images, or transfer bundles.
5. Complete one physical canary per capability on an approved laptop, with executor flags off before and after the canary, correlated task/listener/approval/dispatch/receipt records, and no request-as-success UI state.

Until these blockers close, the truthful state is: request/audit scaffolding implemented, executors disabled and unconfigured, runtime release held.

## Refresh after worker/security remediation — 2026-07-13 23:38 CDT

This section supersedes the earlier test count and resolved findings, but not the HOLD decision.

- Current strict independent suite: **11 passed / 5 expected-failed**.
- Newly verified: worker listener integration, signed executor-name binding, bounded nonce/expiry checks, same-process replay rejection, target-side approval policy, target-side payload validation, fail-closed browser domain allowlist, ambiguous numeric-IP rejection, and DNS/global-address checks.
- Migration 016 is now applied. Migration 017 is pending and may still be corrected before first application.
- Exact remaining blockers:
  1. Per-machine, directional dispatch/receipt key IDs and secrets are implemented in source; deployment still needs provisioning evidence and rotation policy.
  2. Receipt verification must be proven against a real authoritative dispatch and reject mismatched capability/hash fixtures without relying on mocked incomplete request rows.
  3. A completed receipt must be impossible before an authoritative dispatch exists.
  4. Dispatch idempotency must durably reserve and publish through an outbox/idempotency key before any speaker side effect; process memory is not sufficient.
  5. Database receipt uniqueness must be effective (`dispatch_id` or `(request_id,machine_id)`), not include the already-unique surrogate `id`.

Migration 017 should also bind an authenticated principal rather than the request-body `actor`. No authentication dependency currently establishes that identity, so this remains a release blocker even though it is not represented by a separate strict unit characterization.

## Second-pass refresh after directional-key remediation — 2026-07-13 23:55 CDT

This section supersedes the preceding refresh counts and migration state. The implementation remains on **HOLD for executor enablement**.

- Focused implementation plus second-pass security characterization: **24 passed / 4 strict expected-failed** with four FastAPI lifespan deprecation warnings.
- Database migration status: **17 applied / 0 pending**; migration 017 checksum matches `ac44a0867cec5c3b2e3d5264abf6d103011e0616cc7fdd6876199401c299d1e6`.
- PostgreSQL introspection confirms the effective unique index `uq_pet_machine_capability_receipt_request_machine(request_id,machine_id)`, immutable update/delete triggers on dispatch intents and execution nonces, and no PUBLIC table access.
- Source and tests now verify separate per-machine directional environment keys, machine/key-ID binding, receipt-to-authoritative-dispatch hash binding, bounded envelope lifetime, same-process replay rejection, target payload revalidation, disabled-by-default handlers, intent reservation before speaker publication, and worker receipt-before-ack ordering.

The four strict expected failures are the remaining code-level release blockers:

1. **Persistent replay authority is not wired.** `pet_machine_execution_nonces` exists, but `MachineCapabilityExecutor` uses only an in-memory set. Recreating the executor accepts and executes the same valid envelope again.
2. **Dispatch actor is caller asserted.** `PetMachineCapabilityDispatchRequest.actor` is still accepted from the body and no authenticated principal dependency supplies dispatch authority.
3. **Dispatch publication is not transactional.** The durable intent precedes `create_speaker_message`, but no transactional outbox or broker idempotency key closes crash/retry duplication between publication and dispatch finalization.
4. **Key lifecycle authority is absent.** Static `dispatch:<machine>:v1` and `receipt:<machine>:v1` identifiers have no authoritative registry, activation window, rotation overlap, or revocation state.

Additional deployment hardening evidence remains required: use a non-owner runtime database role (the current `aiops` owner retains broad privileges including `TRUNCATE` despite append-only row triggers), provision each directional secret only to its intended service instead of a shared root environment, run PostgreSQL concurrency/restart/rollback probes, and complete one disabled-by-default physical canary with correlated request, approval, intent, speaker message, receipt, and listener evidence.
