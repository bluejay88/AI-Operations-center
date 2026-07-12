# SSH Distribution Runbook

GitHub can distribute the SSH setup scripts, but each Windows laptop must run the setup locally with Administrator rights.

## Why SSH Is Needed

Tailscale confirms that a laptop is reachable, but the Brain PC cannot remotely run update commands until one remote command layer is enabled:

- Windows OpenSSH Server over Tailscale.
- PowerShell Remoting restricted to Tailscale.
- Tailscale SSH if supported and enabled for the device/account.

## Recommended Path

Use Windows OpenSSH Server restricted to the private Tailscale network.

On the Brain PC, enable SSH receiving:

```powershell
cd "C:\Users\jayla\OneDrive\Desktop\Ai Operations Center"
powershell -ExecutionPolicy Bypass -File docker\setup-brain-openssh.ps1
```

On each laptop, after pulling GitHub:

```powershell
cd $env:USERPROFILE\Desktop\AI-Operations-center
powershell -ExecutionPolicy Bypass -File docker\setup-openssh-worker-admin.ps1
```

Then from the Brain PC, test:

```powershell
ssh <windows-user>@<laptop-tailscale-ip> hostname
```

From each laptop, test Brain SSH/API/listener/speaker:

```powershell
powershell -ExecutionPolicy Bypass -File docker\test-brain-ssh-and-api.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -BrainUser <BrainWindowsUsername> -AgentId programmer
```

## Security Rules

- Do not expose SSH to the public internet.
- Restrict Windows Firewall to Tailscale/private network where possible.
- Use strong Windows account credentials or key-based auth.
- Keep SSH access for update/deploy commands only.
- Sensitive actions still require Brain/human approval.
