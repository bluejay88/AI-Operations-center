# Brain runtime profile integration 01

Date: 2026-07-13  
Scope: `BRAIN-01-01` through `BRAIN-01-10`  
Migration: `013_brain_runtime_identity.sql` (`012` is owned by the authoritative PET evidence lane)

## Outcome

The remediated identity and laptop-personality domain models are now composed by a governed, read-only runtime profile service. The service exposes safe identity descriptors, distinct versioned laptop speaking profiles, durable Brain device reservation evidence, governance flags, and readiness gates. It never returns mutation authority and never changes the Brain feature ledger.

Read-only routes:

- `GET /brain-runtime-profile`
- `GET /brain-runtime-profile/readiness`
- `GET /brain-runtime-profile/laptops/{machine_id}`

No `POST`, `PUT`, `PATCH`, or `DELETE` route exists beneath `/brain-runtime-profile`.

## Durable uniqueness and governance

Migration 013 creates `brain_device_identity_reservations`, whose normalized `device_id` primary key makes reservation atomic in PostgreSQL. Rows carry the identity fingerprint, actor, approval reference, and reservation timestamp. Update and delete triggers make reservations append-only. The migration idempotently reserves `brain-gaming-pc` with the reviewed default identity fingerprint.

`PostgresDeviceIdentityRegistry` is an internal adapter, not an API route. It rejects reservation before database access unless constructed with explicit mutation authorization plus a nonempty actor and approval reference. Release is intentionally unsupported pending a separately governed decommission design.

## Readiness truth

`integration_ready` requires the exact ten-feature batch, the durable Brain identity reservation, a machine-inventory/profile match, and read-only/no-mutation API governance. `operational_certified` is always false in this increment, and every response reports ledger state `P`.

Remaining certification gates are physical Brain correlation, a Brain listener receipt, a content-addressed evidence manifest, independent release decision, operational release ID, fresh verification timestamp, and governed compare-and-swap ledger transition. Avatar rendering, real speech synthesis, persisted approved customization, live governed model-profile selection, and enforced output verbosity also require later integration evidence.
