# Brain PC Feature Catalog

Date: 2026-07-13  
Catalog: `brain-feature-catalog-v1`  
Authority: Brain PC capability ledger; additive and independent from task completion and PET release claims

## Scope and identity

The uploaded 500-capability specification is represented as exactly 20 domains with 25 features each. Brain identities are `BRAIN-01-01` through `BRAIN-20-25`; every row retains its one-to-one `PET-01-01` through `PET-20-25` source identity and exact source title. IDs, domain/item positions, source order, catalog hashes, definitions, versions, and state events are immutable.

The generated artifact is `config/brain_feature_catalog_v1.json`. Migration `009_brain_feature_catalog.sql` creates the authoritative relational ledger and seeds it idempotently. `scripts/generate_brain_feature_catalog.py` deterministically regenerates both files from the uploaded UTF-8 source.

## Truth at initialization

| State | Count |
|---|---:|
| Operational (`O`) | 0 |
| Gated (`G`) | 0 |
| Planned (`P`) | 500 |
| Rejected (`R`) | 0 |
| Total | 500 |

Implementation status is `not_started`, evidence status is `none`, and release status is `unreleased` for all 500 initial rows. Existing code, a task completion, a UI label, or a catalog entry is not implementation evidence.

## Evidence and promotion contract

Every version has a feature-specific acceptance criterion and requires at least a test result, audit report, Brain listener receipt, content-addressed artifacts, and physical Brain correlation. Elevated and high-sensitivity capabilities require both Quality and Security review. Self-approval is prohibited by the acceptance contract.

Current status may change only through `transition_brain_feature_state`, which locks the row and uses an expected row version. Events are append-only and idempotency-keyed. A transition to Operational is rejected unless implementation is `implemented`, evidence is `verified`, release is `operational`, and the transition includes an implementation reference, evidence-manifest hash, release ID, and verification timestamp.

## Integration handoff

The shared API should later expose calculated read-only summary and keyset-paginated detail endpoints. API and dashboard integration must read `brain_feature_state_summary`; it must not use constants or task totals. Mutation access should be Brain-only and pass expected row version plus an idempotency key. No shared API or dashboard file is changed by this catalog increment.
