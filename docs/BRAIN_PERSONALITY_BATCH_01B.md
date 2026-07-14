# Brain personality capability batch 01B

Date: 2026-07-13  
Scope: `BRAIN-01-06` through `BRAIN-01-10`

## Exact catalog mapping

| Feature | Catalog title | Implemented software surface |
|---|---|---|
| `BRAIN-01-06` | Adjustable speaking style. | Validated `concise`, `coaching`, `technical`, and `executive` modes. |
| `BRAIN-01-07` | Adjustable formality level. | Independently bounded formality control. |
| `BRAIN-01-08` | Adjustable humor level. | Independently bounded humor control with a low-level no-humor instruction. |
| `BRAIN-01-09` | Adjustable verbosity. | Independently bounded verbosity control translated into a finite response word budget. |
| `BRAIN-01-10` | Different personality for each laptop. | Complete, distinct, fail-closed profiles for Business, Research, and Dev laptops. |

The tenth catalog title does not mention user recognition or authentication, so this batch makes no biometric, recognition, or authorization claim.

## Implementation boundaries

`ai_ops_center.brain_personality_policy` is an immutable pure-policy module. It validates every control, rejects unknown controls and machines, defensively copies profiles into a read-only mapping, requires a distinct profile for every configured laptop, emits deterministic profile fingerprints, and states that style cannot alter permissions, evidence, or approvals. Every policy carries an explicit inventory version that is preserved across adjustments and included in its public evidence payload. Adjustments return a new policy rather than silently mutating shared state.

No API, database, dashboard, migration, remote machine, or deployed runtime is changed by this batch.

## Test and evidence status

The focused tests verify exact IDs, per-laptop distinctness, independent adjustment, invalid-value rejection, missing/unknown/duplicate profile rejection, caller-safe immutability, inventory-version preservation, fail-closed lookup, authority-boundary language, and a public payload without certification claims.

All five authoritative rows remain **Planned (`P`)**. The code and automated tests are implementation evidence, not operational certification. Promotion still requires physical Brain correlation and a Brain listener receipt, a content-addressed evidence manifest with the required artifacts, independent Quality review, an operational release ID, fresh verification, and the governed ledger transition. None is fabricated or self-approved here.
