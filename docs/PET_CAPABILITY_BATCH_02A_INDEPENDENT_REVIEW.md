# Independent security and rubric review — PET batch 02A

Date: 2026-07-13  
Reviewer role: independent Quality/Security audit  
Scope: `PET-02-04` through `PET-02-08`  
Decision: **HOLD — not certified, not releaseable, no ledger transition authorized**

## Ground truth

The five catalog rows remain `P` (planned). At review start, the implementation consisted of a standalone verifier and evaluator. During the review, concurrent implementation added migration `010_pet_instruction_replay_guard.sql`, `PostgresReplayGuard`, and a worker speaker-intake call to `verify_instruction`. The review was refreshed against that new snapshot. These additions are not deployed or physically evidenced in this review, and the repository `.env` has no nonempty `BRAIN_INSTRUCTION_SECRET`; signed instructions therefore fail closed rather than operate.

After the concurrent replay work landed, two of the four hashes in `PET_CAPABILITY_BATCH_02A.md` became stale: `pet_instruction_protocol.py` and `test_pet_instruction_protocol.py` no longer match the documented digest. The certification artifact gate therefore does not pass for the current source snapshot until a new immutable submission is created. The refreshed implementation suite (protocol, evaluator, and worker intake) passes 19 tests; seven independent negative-characterization tests remain expected failures. Passing tests establish deterministic behavior only; they do not establish physical execution, independent evidence, or release readiness.

## Findings

### Critical — certification inputs are assertions, not correlated evidence

`evaluate_capability_batch` treats any positive task/listener/peer integers, any producer string, reviewer-name strings, submitter-provided rubric scores, a nonempty test-report string, and submitter-provided `brain_decision="release"` as passing evidence. It does not query the database, verify that the records exist, confirm common task/machine/feature ownership, validate freshness or terminal status, authenticate reviewers, open/hash the test report, or read an append-only Brain decision. A fabricated submission can consequently become `release_candidate`.

The evaluator still returns `ledger_transition_authorized: false`, which prevents it from directly promoting the ledger. That safeguard must remain, but the misleading release-candidate result blocks certification until every gate is resolved from authoritative records.

### High — new worker integration is incomplete and not physically evidenced

The worker now verifies only `brain_instruction`, `signed_instruction`, or messages already carrying an envelope. That is a useful fail-closed boundary for those message types. However, an accepted instruction is only acknowledged through the existing generic receipt path: its decision, instruction ID, signer, and verified envelope hash are not attached to the listener receipt, and its payload is not bound to a fenced task or immutable execution snapshot. The test mocks the verifier and proves routing, not real signing, database consumption, execution, or a physical round trip. Any future actionable message types outside this two-name allowlist could bypass the signature requirement.

### High — replay protection is process-local

Migration 010 appeared during this review and improves the design with a `(signer_id, nonce)` primary key and atomic `INSERT ... ON CONFLICT DO NOTHING`. The Python guard calls the database function. Current tests inspect SQL text and mock one successful call; they do not execute the migration or prove concurrent database behavior.

The table is described as audit evidence but has no append-only update/delete trigger, no pruning/audit policy, and no role grants/revocations. PostgreSQL functions are executable by `PUBLIC` by default unless revoked, and the application uses the same broad database identity. A caller able to invoke the function can pre-consume a guessed nonce for denial of service; a caller able to delete rows can re-enable replay. The record also lacks an envelope hash, so it cannot prove exactly what bytes were verified.

The rollback-only database review confirmed first claim `true`, same signer/nonce replay `false`, a different signer with the same nonce `true`, and an expired claim `false`. It also confirmed that the application database role could delete both inserted audit rows. The entire audit transaction was rolled back.

Before certification, extend the database evidence with an envelope hash; enforce append-only mutation controls; revoke table writes and function execution from `PUBLIC`; grant only a dedicated worker role; provide bounded audited pruning after expiry/skew; and fail closed on storage errors. Required integration tests include concurrent database consumers with exactly one winner, separate processes, restart persistence, wrong-signer/target isolation, unauthorized SQL roles, attempted update/delete, database outage, expiry boundary, and rollback behavior.

### High — malformed signed content can raise instead of fail closed

The parser accepts any nonempty `dict` payload, then canonical JSON serialization can raise for unsupported values or mixed key types. `verify_instruction` does not catch that error. An authenticated signer or hostile in-process caller can turn malformed input into an exception at the trust boundary. Payload size, nesting, finite-number rules, action schema, and allowed operations are also unbounded/unvalidated. Cross-language canonical JSON behavior is unspecified.

Before integration, use a strict JSON-compatible schema and bounded serialized size/depth; reject non-finite numbers and unsupported types; catch canonicalization errors; define a cross-language canonicalization contract; and authorize signer/target/action combinations, not merely possession of any resolver-known secret.

### High — evaluator scope and peer requirement are caller-controlled

The catalog gate accepts any unique set of one to five valid IDs rather than the exact five-feature batch manifest. The submitter can set `requires_peer_response=false` and satisfy physical evidence without a peer response, contrary to this batch's documented release sequence. The batch manifest and required evidence policy must be evaluator-owned/versioned inputs.

### Medium — hardcoded state and incomplete evidence binding

The evaluator always reports `current_ledger_state="P"` instead of reading the current row/version. Artifacts are not bound to a commit, test run, task, listener receipt, peer response, reviewer decisions, or one immutable submission manifest. There is no evidence freshness window. This risks stale or cross-submission evidence reuse after later ledger states exist.

## Independent rubric

| Dimension | Score | Review basis |
|---|---:|---|
| Requirements | 62 | Core verification and a worker receipt boundary now exist, but accepted payloads are not executed/bound and action payloads remain unvalidated. |
| Security | 48 | Constant-time HMAC and an atomic database key are positive; database privileges/immutability, authorization, evidence authenticity, malformed-input handling, and key lifecycle remain unresolved. |
| Reliability | 52 | Deterministic and in-memory concurrency tests pass; real database concurrency, restart, outage, and physical-machine behavior are untested. |
| Usability/accessibility | 70 | Decision codes are concise, but no operator-facing correlated diagnostic or integrated path exists. |
| Auditability | 40 | File hashes and nonce identifiers are reproducible; accepted receipts lack envelope binding and submitted evidence/reviews/Brain decision remain unauthenticated. |
| Rollback | 45 | A rollback sentence exists, but there is no actual integration/canary to disable and no tested rollback evidence. |

Average: **52.83 / 100**. Every dimension must be at least 80 and the average at least 90. This review fails both thresholds and does not self-approve.

## Required blockers before a new review

1. Harden and transactionally test migration 010 with envelope binding, append-only controls, least privilege, pruning, real concurrency, restart, and outage cases.
2. Complete the worker intake by recording the verified decision/hash and binding an immutable verified payload to fenced execution; configure a rotated 32+ byte secret through approved secret management.
3. Validate bounded payload schema, canonicalization, signer authorization, key ID/rotation/revocation, and exception-safe failure codes.
4. Make the evaluator load the exact batch manifest and evidence policy from a versioned authority, with no submitter bypass.
5. Resolve task, listener, peer, heartbeat, reviewer, rubric, test report, Brain decision, ledger row/version, and artifacts from authoritative records and bind them to one immutable evidence manifest.
6. Run concurrency/restart/outage/security tests plus valid, tampered, expired, wrong-target, and replay probes on a healthy physical laptop.
7. Obtain separate authenticated Quality and Security reviews, then a real append-only Brain canary decision.

Until all seven blockers are evidenced, the truthful count remains `O/G/P/R = 0/0/5/0` for this batch.
