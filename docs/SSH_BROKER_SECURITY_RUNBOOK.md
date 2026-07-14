# SSH diagnostic broker security runbook

## Invariants

- Models, dashboards, API containers, and device browsers never receive SSH private keys.
- One Brain Ed25519 identity and one envelope key are used per target node.
- Nodes accept SSH only from the Brain Tailscale `/32` address and only as `aiops-diagnostic`.
- Every diagnostic requires a Jayla approval record and target-side signature, expiry, target, command, argument, and nonce validation.
- Raw SSH commands, interactive shells, forwarding, tunnels, and administrator automation accounts are prohibited.

## Initial Brain provisioning

1. Run `docker/initialize-control-plane-security.ps1` locally. Do not display `.env`.
2. Run `docker/initialize-brain-ssh-identities.ps1` as Administrator.
3. Verify each node's Ed25519 host-key fingerprint on the physical node console or through a previously authenticated channel.
4. Run `docker/pin-ssh-host-key.ps1` with that exact verified fingerprint. Never use `accept-new`.

## Target provisioning order

Perform these steps through a previously authenticated encrypted channel or on the physical node. Never put a secret in a process argument.

1. Install the scoped API token with `docker/install-device-api-token-admin.ps1 -MachineId <id> -DeviceTokenFromStdin`.
2. Install the target-specific envelope key with `docker/install-ssh-broker-envelope-key-admin.ps1 -MachineId <id> -KeyFromStdin`.
3. Copy only the target's `.pub` identity and the hardened scripts.
4. Run `docker/setup-worker-openssh-tailscale-admin.ps1 -AllowedRemoteAddress 100.70.49.32/32 -BrainPublicKeyFile <pub-file>`.
5. Confirm the firewall remote address, non-administrator account, `sshd -t`, and forced-command path locally.
6. Start `ai_ops_center.device_gateway` on loopback and verify device-scoped API access.

The setup script validates configuration before restarting and restores its backup if restart fails. It refuses to harden SSH until machine identity and envelope authority are installed.

## Approved execution

1. Create a typed request through `POST /ssh-broker/requests`.
2. Jayla reviews and approves the associated approval record using a fresh dashboard session.
3. `POST /ssh-broker/execute` reports only that the operation is authorized for the isolated host broker; it cannot execute SSH.
4. On the Brain host, the isolated operator runs `python -m ai_ops_center.cli ssh-broker-execute --operation-id <id> --actor jayla-operator`.
5. Review the append-only execution record, hashes, target/key fingerprints, exit status, duration, and redacted output.

## DEV recovery after the 2026-07-14 first cutover

On DEV, open PowerShell as Administrator and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<repo>\docker\rescue-local-sshd-config.ps1"
```

Then return to the target provisioning order above. Do not delete the backup config, broaden the firewall, or re-enable passwords to recover access.

## Kill switch

Use the human-only kill-switch endpoint with an evidence-rich reason. The switch blocks broker execution. For a full fleet stop, also revoke the Brain public keys on nodes and disable the Brain `/32` firewall rules through the approved node-management channel.
