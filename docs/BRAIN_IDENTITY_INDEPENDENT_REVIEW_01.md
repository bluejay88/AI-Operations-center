# Independent Quality and Security review: Brain identity batches 01/01B

Date: 2026-07-13  
Scope: `BRAIN-01-01` through `BRAIN-01-10`  
Reviewer role: independent Quality/Security review; no implementation ownership, ledger mutation, or release authority

## Executive summary

The two modules are useful, well-bounded **domain-model prototypes** with strong input validation and focused automated tests. The exact catalog IDs and titles are correctly mapped. None of the ten features is operationally certified: no module is integrated into the live Brain API/model/speech/dashboard path, no physical Brain execution was observed, and the catalog-required listener receipt, evidence manifest, operational release, and verification data are absent.

Review result: **changes requested before runtime integration**. Two medium findings from the first pass were remediated in this local batch: PET display names now use a conservative grammar, and laptop personality profiles are defensively copied into a read-only mapping. `BRAIN-01-02` still needs an authoritative atomic registration design before runtime integration because uniqueness is currently a preflight check.

## Catalog and evidence audit

All ten rows require `test_result`, `audit_report`, and `brain_listener_receipt`; at least three content-addressed artifacts; physical Brain correlation; and independent Quality review. Self-approval is prohibited. The current batch provides source, tests, and this audit report, but it does not provide a listener receipt, physical correlation, an evidence-manifest hash, release ID, or fresh operational verification. Therefore every row must remain **Planned (`P`)**.

The scores below measure review readiness, not ledger state. A score cannot authorize promotion.

| ID | Software readiness /100 | Review disposition | Principal blocker |
|---|---:|---|---|
| `BRAIN-01-01` | 62 | Integration-ready after mitigation | Conservative display-name grammar added; runtime prompt integration still unproven. |
| `BRAIN-01-02` | 48 | Design change required | Collision check depends on a caller snapshot; no authoritative atomic registration. |
| `BRAIN-01-03` | 50 | Integration-ready | Validated descriptor only; no renderer/runtime demonstration. |
| `BRAIN-01-04` | 50 | Integration-ready | Validated descriptor only; no speech-engine/runtime demonstration. |
| `BRAIN-01-05` | 57 | Integration-ready | Adjustment is not persisted or applied to a live governed model call. |
| `BRAIN-01-06` | 59 | Integration-ready | Generated instruction is not wired to a live model/speech route. |
| `BRAIN-01-07` | 59 | Integration-ready | Same runtime and physical-evidence gap. |
| `BRAIN-01-08` | 59 | Integration-ready | Same runtime and physical-evidence gap. |
| `BRAIN-01-09` | 59 | Integration-ready | Word budget is advisory and not output-enforced. |
| `BRAIN-01-10` | 58 | Integration-ready after mitigation | Mapping is now defensively read-only; laptop list is still static and has no live routing proof. |

Rubric weights used per feature: catalog fidelity 10, implementation depth 25, automated tests 20, security/authority boundaries 15, runtime/physical proof 15, release/evidence completeness 15. Runtime/physical proof scores zero for every row. Release/evidence completeness receives only partial credit for documentation and this review; it does not meet the transition contract.

## Findings

### Remediated medium - SEC-01: nested mapping defeats policy immutability

`LaptopPersonalityPolicy` is frozen, but its `profiles` field accepts a caller-owned `Mapping` (`ai_ops_center/brain_personality_policy.py:71-84`) without a defensive copy or read-only wrapper. A caller can mutate the original dictionary after validation, bypassing the distinct-profile invariant and changing live behavior without a new fingerprinted policy object. Impact is currently limited because the module is not wired into runtime; it becomes high impact if used as an authorization-adjacent shared policy.

Remediation added: the policy now defensively copies profiles into a read-only `MappingProxyType`, with tests for caller-dictionary mutation and exposed-field mutation.

### Remediated medium - QA-01: PET name crosses a prompt boundary as raw text

The name validator rejects control characters (`ai_ops_center/brain_identity.py:90-95`), but arbitrary printable text is placed directly into `prompt_context()` (`ai_ops_center/brain_identity.py:129-136`). A value such as an instruction-like sentence remains valid. The hard-coded safety sentence helps but is not a data/instruction boundary.

Remediation added: PET names now use a conservative display-name grammar. Downstream governed prompts must still enforce safety independently.

### Medium — QA-02: device uniqueness is check-then-act only

`assert_unique_device_identity()` compares against an iterable snapshot (`ai_ops_center/brain_identity.py:112-115`). It is case-insensitive and useful for preflight validation, but two callers can pass simultaneously. It cannot satisfy authoritative uniqueness alone.

Required remediation: enforce normalized device identity with a database unique constraint or transactional registry operation at the future persistence boundary. Keep the current method as preflight UX only.

### Low — QA-03: fixed laptop inventory can drift

`KNOWN_LAPTOPS` is hard-coded (`ai_ops_center/brain_personality_policy.py:17`) instead of derived from the authoritative machine registry. The current three IDs match configuration, but a fleet change can make the policy reject a legitimate laptop or omit a new one.

Required remediation: pass an explicit, trusted registry snapshot into policy construction and include registry version/fingerprint in evidence.

### Informational — QA-04: descriptor and instruction are not runtime capabilities

Avatar, voice, personality, and speaking profiles validate configuration but do not render an avatar, synthesize speech, persist adjustments, select profiles in live routing, or enforce generated word budgets. This is correctly described in the batch docs. Integration tests must prove these boundaries before any “implemented and deployed” claim.

## Adversarial test evidence

`tests/review_test_brain_identity_batches.py` adds passing negative controls for the remediated display-name and mapping-immutability issues. The Python security-review skill had no framework-independent Python reference file, so this review applies its general secure-default guidance and repository-specific threat boundaries.

## Required evidence before any state promotion

1. Implement atomic uniqueness for `BRAIN-01-02` at the authoritative persistence boundary.
2. Integrate profiles into governed Brain runtime paths with authorization boundaries unchanged.
3. Run feature-specific integration tests and physical Brain canaries, including laptop-specific route selection and real speech/avatar behavior where applicable.
4. Record Brain listener receipts correlated to immutable artifacts and test results.
5. Produce a content-addressed evidence manifest with at least three required artifacts per feature.
6. Obtain a separate release decision, operational release ID, and fresh verification timestamp.
7. Use only the governed compare-and-swap ledger transition; this review does not authorize it.
