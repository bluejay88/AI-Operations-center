# SSH onboarding diagnostic markers

Laptop onboarding and connectivity scripts emit one-line, machine-readable markers in this form:

```text
AI_OPS_DIAGNOSTIC={"schema":"ai-ops.diagnostic-marker.v1",...}
```

Consumers should parse only the JSON after `AI_OPS_DIAGNOSTIC=`. Human-readable console text may change; marker `code` values are stable routing keys. Markers are also included in laptop diagnostic JSON and workstation-update payloads under `diagnostic_markers`, and Brain-to-laptop connection metadata under `diagnostic_marker`.

Current SSH codes include:

- `SSH_READY` and `SSH_INBOUND_READY_FOR_BRAIN_TEST`
- `SSH_IDENTITY_MISSING`
- `SSH_HOST_KEY_REJECTED`
- `SSH_PUBLIC_KEY_REJECTED`
- `SSH_HOST_UNRESOLVED`
- `SSH_NETWORK_UNREACHABLE` and `SSH_PORT_22_BLOCKED`
- `SSH_SERVICE_MISSING`, `SSH_SERVICE_STOPPED`, and `SSH_SERVICE_NOT_LISTENING`
- `SSH_FIREWALL_RULE_MISSING`
- `SSH_AUTHORIZED_KEY_MISSING` and `SSH_AUTHORIZED_KEY_UNVERIFIED`
- `SSH_HANDSHAKE_FAILED`

The top-level onboarding workflow also emits `ONBOARDING_COMPLETE` or `ONBOARDING_PHASE_FAILED`. The failure marker's `phase` identifies `install_prerequisites`, `install_chatgpt`, `join_worker`, or `benchmark`, so the Brain can route the marker without scraping prose.

Security boundaries remain mandatory: never place a private key in telemetry, Git, console output, or an API payload; verify host and public-key fingerprints out of band; keep inbound SSH limited to the Tailscale address range; and use `BatchMode=yes` for automation so a job cannot hang on a password prompt.
