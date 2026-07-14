# Governed per-machine PET capability contracts

Date: 2026-07-13  
API: `GET /pet-machine-capabilities/contracts`, `POST /pet-machine-capabilities/requests`  
Persistence: migrations `015_pet_machine_capability_requests.sql` and `016_pet_machine_capability_dispatch.sql`

These server-side contracts target an exact configured machine and assigned PET. Supported requests are public-web browser navigation, local music playback controls, and device-hosted model chat. They are not UI simulations and they do not directly launch a browser, control a media player, or claim a model response.

Browser and music requests always create a Brain approval request and send only an `approval_hold` worker envelope stating `DO NOT EXECUTE`. Device-hosted model chat may enter the device executor queue because it grants no OS or external-control authority, but completion still requires a later machine-originated receipt. Every submission creates listener and speaker records and an append-only PostgreSQL request row. Caller success assertions are ignored; the submission response always has `success_claimed: false` and no receipt ID.

## Docker/server configuration

The API container uses its existing `DATABASE_URL` connection to PostgreSQL and the existing listener/speaker/approval tables. Migration 015 depends on migrations 012 and 014 for the shared append-only authority trigger and action-evidence schema. No Docker socket, host browser, audio device, privileged mode, host filesystem path, or remote-control port is mounted into the API container.

Optional API-container environment:

- `PET_BROWSER_ALLOWED_SCHEMES=https` by default; may contain only `http,https`.
- `PET_BROWSER_ALLOWED_DOMAINS=` is empty by default, allowing public DNS hosts. Set a comma-separated domain allowlist for a tighter deployment.

URLs reject non-HTTP schemes, credentials, fragments, localhost, `.local`, and non-public literal IPs. Music accepts only controlled commands and safe device-local media IDs, never filesystem paths or URLs. Model chat accepts a bounded prompt and safe local model ID.

Approved execution uses a second dispatch phase. The Brain re-reads approval state, signs a target-specific envelope with HMAC-SHA256, and sends it to the exact machine. `MachineCapabilityExecutor` verifies signature, target, and authority on the host. Browser, music, and model-chat capability flags all default to disabled; handlers must be injected by the target-host package. The API server contains no OS launch implementation.

Set per-machine directional keys instead of one shared secret: Brain dispatch uses `PET_DISPATCH_SIGNING_KEY_<MACHINE_ID>`, target workers verify with `PET_DISPATCH_VERIFY_KEY_<MACHINE_ID>`, workers sign receipts with `PET_RECEIPT_SIGNING_KEY_<MACHINE_ID>`, and Brain verifies receipts with `PET_RECEIPT_VERIFY_KEY_<MACHINE_ID>`. These are intentionally unset by default, so dispatch and receipt ingestion fail closed. Machine executors return signed `held`, `completed`, or `failed` receipts. Migrations 016 and 017 store dispatches, dispatch intents, nonces, and receipts append-only with idempotency safeguards. Status reads identify machine-reported completion but never label it independently verified. Physical target-host tests and an independent receipt audit remain required before any feature certification.

Worker execution flags default to false: `PET_ENABLE_BROWSER_NAVIGATION`, `PET_ENABLE_MUSIC_LIBRARY`, `PET_ENABLE_MUSIC_PLAYBACK`, and `PET_ENABLE_DEVICE_MODEL_CHAT`. The worker consumes only `pet_capability_signed_execution`, verifies its target/signature/executor mapping, checks for an existing receipt before invoking a handler, records the signed receipt, and acknowledges the exact speaker message. Built-in target-host handlers are registered only for capabilities whose flags are explicitly enabled; deployments may still register a narrower custom handler.

Browser navigation opens only the already validated URL through the host default browser. Music indexing is bounded to `PET_MUSIC_LIBRARY_ROOT` (or the current user's `Music` directory), excludes symlinks and unsupported extensions, and exposes only opaque IDs plus sanitized title/artist metadata—never filesystem paths. Named playback resolves only within that index. Pause, resume, stop, next, and previous are held honestly when there is no controllable playback session. Device model chat uses `PET_DEVICE_OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`) and `PET_DEVICE_OLLAMA_MODEL`; non-loopback endpoints are rejected and cloud fallback is never attempted.
