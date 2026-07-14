# PET Governed Device Tools

## Contract

Every Dev, Research, and Business mini dashboard uses the shared PET device-tools surface. PET identity remains machine-specific: Dev maps to `development-pet`, Research to `research-pet`, and Business to `creative-pet`.

All controls use the authoritative `POST /pet-machine-capabilities/requests` endpoint and read policy from `GET /pet-machine-capabilities/contracts`.

| Capability | Capability type | Server evidence | Truth displayed |
|---|---|---|---|
| Open local browser URL | `browser_navigation` | Append-only request, approval, listener event, speaker hold | `pending_approval`, request/approval IDs, `success_claimed=false`; acceptance never means the browser opened |
| Local music play/pause/stop | `music_playback` | Append-only request, approval, listener event, speaker hold | Request/approval IDs and false success claim; playback requires a later machine receipt |
| Chat with device-hosted model | `device_model_chat` | Append-only request plus targeted device-model speaker message | `requested`, speaker ID, `success_claimed=false`; response requires a later machine receipt |

## URL and media validation

Client validation mirrors the advertised server contract where possible:

- maximum 2,048 URL characters and no control characters;
- advertised HTTP(S) scheme policy (`https` by default);
- host required; credentials and fragments denied;
- localhost, `.local`, and common private IPv4 ranges denied;
- advertised domain allowlist enforced when configured;
- server validation remains authoritative and fails closed.

Music Play requires a safe device-library media ID. Paths and URLs are not accepted. Pause and Stop operate on the active local session only after approval and worker execution.

## Governance and receipts

- Every action requires a click or form submission.
- Browser and music requests are held for approval with a `DO NOT EXECUTE` worker envelope.
- Approval does not equal completion.
- Device-model requests target the device-hosted executor with a safe model ID; this UI does not call cloud-model or legacy collaboration endpoints.
- Readiness distinguishes API path, worker state, unverified executor, request status, and machine receipt.
- No UI code calls `window.open`, controls media directly, or reports success merely because the API accepted a request.

## API and Docker expectations

The mini dashboard and API share the deployed port `8088` origin so CSP `connect-src 'self'` permits requests. The deployed API container requires:

- unique `GET /pet-machine-capabilities/contracts` and `POST /pet-machine-capabilities/requests` routes;
- applied migration `015_pet_machine_capability_requests.sql`;
- PostgreSQL tables for capability requests, approvals, listener events, and speaker messages;
- connected laptop workers that can return machine-originated receipt evidence.

Docker/API health proves the governed request path only. Browser launch, media control, and device-hosted inference require separate worker support and physical evidence.

## Verification

```powershell
node --check laptop_packages/shared/mini-dashboard.js
python -m pytest tests/test_pet_device_tools.py tests/test_pet_machine_capabilities.py -q
docker compose config
```

## Release boundary

This is implemented governed-request infrastructure, not physical certification. Feature-ledger entries remain planned until each laptop returns independently reviewed browser, music, and local-model receipts.
