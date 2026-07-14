# PET machine runtime security runbook

## Release state

Migration 018 closes the runtime architecture gaps without changing applied migrations 001-017. It adds an atomic, restart-durable execution nonce claim; an idempotent transactional speaker outbox; and a directional-key registry with activation, expiry, revocation, and append-only events. Production startup fails closed when this authority is not provisioned. All browser, music, library, and device-model executors remain disabled by default.

## Provision a new key generation

1. Run `python scripts/generate_pet_capability_secrets.py --output .env.pet-secrets.next`. The generator uses OS cryptographic randomness, creates the file exclusively with restrictive permissions, and never prints secret values. The filename is gitignored.
2. Put the generated values into the machine/server secret store. Do not commit them, send them through PET chat, or put them in Docker Compose YAML.
3. For every machine, register the dispatch and receipt key IDs through `register_machine_capability_key`. The function stores only SHA-256 fingerprints, not secrets. Use a short overlap window and an authenticated operator identity.
4. Set `PET_KEY_REGISTRY_REQUIRED=true`; restart the API/worker; verify `/pet-machine-capabilities/contracts`; run one held canary while all executor flags remain false.
5. Enable only the required executor on only its target host after its physical canary passes. Never enable an API-container host executor.
6. Revoke the old key ID with `revoke_machine_capability_key`, supplying an authenticated actor and reason. Confirm a message signed by the revoked generation is held.
7. Securely delete the temporary secret file after the secret store and target hosts are updated.

Rotation is a new key ID and new secret. Reusing a key ID, changing only an environment secret beneath an existing fingerprint, or deleting lifecycle evidence is prohibited.

## Conservative browser allowlist

Provision `PET_BROWSER_ALLOWED_SCHEMES=https`. A suitable starting allowlist for the requested workflows is:

`PET_BROWSER_ALLOWED_DOMAINS=chatgpt.com,openai.com,youtube.com`

The validator accepts each exact host and its subdomains, rejects credentials/fragments, localhost, `.local`, ambiguous numeric hosts, and non-public IP literals. Add a domain only after review. An empty list is reported as `allowlist_configured=false` by `/pet-machine-capabilities/contracts` and browser requests fail closed.

## Transaction and replay invariants

- `publish_pet_machine_capability_dispatch` reserves the immutable intent, outbox row, speaker message, and dispatch record in one PostgreSQL transaction.
- The idempotency key is `pet-capability-dispatch:<request UUID>` and has a unique speaker index. Retries return the existing speaker message.
- `consume_pet_machine_execution_nonce` accepts a nonce only when its machine, request, dispatch hash, and unexpired authoritative intent match. Its `(machine_id, nonce)` primary key survives process and host restarts.
- A replay-store error is not downgraded to memory; the worker does not execute or acknowledge the signed command.
- Completion is still only a signed machine report and never an independently verified success claim.

## Enablement checklist

- Migrations 001-018 applied with matching checksums.
- Production authentication configured; dispatch body contains no actor field.
- Four directional values per machine injected from a secret store and fingerprints registered.
- Old generation revoked after overlap canary.
- Browser allowlist is explicit and `/contracts` reports it accurately.
- Executor flags false until browser/music/microphone/speaker/model/restart/accessibility canaries pass on that physical machine.
- A replay of the same signed envelope is held after worker restart.
- A repeated dispatch produces one outbox row and one speaker message.
