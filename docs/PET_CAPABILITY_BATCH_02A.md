# PET capability batch 02A — instruction trust boundary

Date: 2026-07-13  
Decision: implementation verified; release held  
Catalog state: all five features remain `P` (planned)

## Exact catalog scope

| Feature ID | Source title | Implemented contract |
|---|---|---|
| `PET-02-04` | Reject invalid instructions. | Required fields, identifiers, timezone-aware timestamps, and nonempty object payload fail closed. |
| `PET-02-05` | Verify signed instructions. | HMAC-SHA256 verification uses canonical JSON, a minimum 32-byte signer secret, and constant-time comparison. |
| `PET-02-06` | Confirm instruction expiration. | Expired, inverted, future-issued, and policy-excessive TTL envelopes are rejected. |
| `PET-02-07` | Confirm device targeting. | A validly signed envelope must match the receiving machine exactly. |
| `PET-02-08` | Detect replayed instructions. | A thread-safe guard atomically consumes each valid nonce once and expires old nonce records. |

This batch was selected because the five abilities form one enforceable boundary before any PET accepts remote Brain work. It is narrower and more defensible than claiming that the entire Brain Communication domain works.

## Implementation and test evidence

| Artifact | SHA-256 |
|---|---|
| `ai_ops_center/pet_instruction_protocol.py` | `55d12ec7a0eec01de6d8fe95238827da21912ba735a3df71531d3d5848693ea9` |
| `ai_ops_center/pet_capability_certification.py` | `6ca5e64e131739674148a05721a089b51d8090355f758e069b7eca9c55f7f364` |
| `ai_ops_center/worker.py` | `4c5103021d4bcc33ef13cf8f99e2a2f4f6706796e35dabfe31ea205fe1743eea` |
| `sql/migrations/010_pet_instruction_replay_guard.sql` | `f784945578dffc1168403053fb3cb10d682d995dfbb82ddcdf4c07f3561f636a` |
| `docker/audit_pet_instruction_replay.py` | `78113599de71850d81f5e24d3b6ac2e02dd03815df94a9f123c54c450afabafd` |
| `tests/test_pet_instruction_protocol.py` | `19a5340aa31cf88d278bd3aac061b28717c7ae057cdbe6d871fa16928f7fa8c8` |
| `tests/test_pet_capability_certification.py` | `7a692d8e5e55828b633987bde00692d3d60fef3fdfb17eb95fb8c74a83292838` |
| `tests/test_worker_instruction_intake.py` | `8841f9d09e7c6997344639b2d815b7ad0958614866bcddf729bab9b03d7bcb9a` |

Focused result: `19 passed in 1.28s`.  
Full repository result after integration: `80 passed in 3.13s`, with four pre-existing FastAPI lifespan deprecation warnings.

The generic evaluator validates a maximum five-feature catalog batch, repository-contained artifact paths and hashes, nonzero passing tests, correlated physical task/listener/peer evidence, independent Quality and Security reviewers, six rubric dimensions, rollback, and Brain decision. It deliberately returns `ledger_transition_authorized: false`; only the transactional Brain release path may change `P` to `O`.

## Current gate readout

| Gate | Result | Reason |
|---|---|---|
| Catalog contract | Pass | All five immutable IDs and source titles exist in catalog v1. |
| Implementation artifacts | Pass | Modules exist and their recorded hashes match. |
| Deterministic tests | Pass | 13 focused tests, zero failures. |
| Rollback definition | Pass | Disable the instruction intake integration and restore the prior worker entry point. |
| Physical machine evidence | Hold | No target laptop has yet returned correlated task, listener, and peer IDs for this batch. |
| Multi-process replay durability | Partial pass | Migration 010 provides a `(signer_id, nonce)` primary key and one atomic `INSERT ... ON CONFLICT` function. Migration 010 is applied with checksum `f784...636a`; the separate live 40-way audit remains unexecuted because command approval was unavailable. |
| Worker intake integration | Pass in tests / not deployed | Signed instruction types and messages carrying an envelope fail closed before acknowledgement; ordinary messages preserve their existing receipt path. Container images were not rebuilt by this batch. |
| Independent Quality/Security review | Hold | This implementation team cannot approve its own work. |
| Brain decision | Hold | No release or successful canary decision has been appended. |

## Required release sequence

1. Run `docker/audit_pet_instruction_replay.py` when command approval is available and retain its 40-way database race result.
2. Configure a strong `BRAIN_INSTRUCTION_SECRET` through the approved secret channel; never place it in source or evidence.
3. Rebuild the worker image, then run valid, tampered, expired, wrong-target, and replay probes on one healthy physical laptop.
4. Return correlated task, listener, peer-response, heartbeat, and test artifact IDs to Brain.
5. Have `rubric-auditor` and `security-monitor` review independently, with every dimension at least 80 and average at least 90.
6. Brain chooses canary or hold. Only a passed canary may request the five item-level ledger transitions.

## Reusable batch rule

Later teams should submit no more than five exact catalog IDs per certification call. Implementation proof can advance the evidence phase, but missing physical proof, independent review, or Brain release always leaves the catalog count unchanged.
