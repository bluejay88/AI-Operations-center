# Brain identity capability batch 01

Date: 2026-07-13  
Scope: `BRAIN-01-01` through `BRAIN-01-05`

## Implemented software surface

`ai_ops_center.brain_identity` provides an immutable, validated Brain PET identity profile:

| Feature | Capability implemented in code |
|---|---|
| `BRAIN-01-01` | A validated, prompt-safe PET display name limited to three conservative name tokens and serialized as data in prompt context. |
| `BRAIN-01-02` | A DNS-style device identity plus an atomic registry abstraction and concurrency-safe in-memory adapter. |
| `BRAIN-01-03` | A custom avatar descriptor with archetype, accessible alt text, accent color, and depth style. |
| `BRAIN-01-04` | A custom voice profile with voice ID, locale, rate, pitch, and volume validation. |
| `BRAIN-01-05` | Immutable personality adjustment across warmth, directness, formality, humor, and verbosity. |

The profile has a deterministic SHA-256 fingerprint, a redaction-safe public payload, and prompt context that explicitly prevents personality settings from overriding safety or approval rules. No database, dashboard, or migration surface is changed by this batch.

## Verification and honest ledger state

Automated tests cover exact catalog mapping, deterministic identity, invalid identifier rejection, atomic device collision rejection, concurrent reservation, avatar/voice validation, immutable bounded personality changes, and safety scoping.

All five ledger rows must remain **Planned (`P`)**. This batch supplies implementation and automated-test artifacts only. The catalog contract additionally requires a physical Brain listener receipt, content-addressed evidence manifest, independent Quality review, operational release ID, and a fresh verification timestamp. None is fabricated here; no ledger mutation or deployment claim is made.

## Integration handoff

The runtime can instantiate `BrainIdentityProfile.from_mapping(...)`, call `reserve_device_identity(...)` against a `DeviceIdentityRegistry`, use `prompt_context()` as a governed style prefix, and expose `public_payload()` to trusted presentation layers. The included in-memory registry is concurrency-safe for one process; a future persistence adapter must preserve atomic `reserve()` semantics with a normalized unique constraint. Persistence and API exposure require a separately reviewed integration because they change shared runtime surfaces.
