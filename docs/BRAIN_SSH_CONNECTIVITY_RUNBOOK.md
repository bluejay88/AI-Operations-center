# Brain SSH Connectivity Runbook

This runbook sets up the Gaming PC / Brain PC to receive SSH securely over Tailscale and gives each laptop a test command for send/receive verification.

## Brain PC Setup

Run this from the AI Operations Center repo on the Brain PC:

```powershell
cd "C:\Users\jayla\OneDrive\Desktop\Ai Operations Center"
powershell -ExecutionPolicy Bypass -File docker\setup-brain-openssh.ps1
```

Approve the Windows Administrator prompt.

The script:

- Installs Windows OpenSSH Server if missing.
- Starts `sshd`.
- Sets `sshd` to start automatically.
- Adds a Windows Firewall rule for TCP `22`.
- Restricts the rule to Tailscale addresses only: `100.64.0.0/10`.

## Brain Connection Information

- Brain Tailscale IP: `100.70.49.32`
- Brain API: `http://100.70.49.32:8088`
- Brain dashboard: `http://100.70.49.32:8088/dashboard/`
- Brain listener endpoint: `POST http://100.70.49.32:8088/listener/events`
- Brain speaker endpoint: `GET http://100.70.49.32:8088/speaker/feed/{machine_id}`
- SSH target format: `<BrainWindowsUsername>@100.70.49.32`

To find the Brain Windows username on the Brain PC:

```powershell
$env:USERNAME
```

## Laptop Connectivity Test

After pulling the repo on each laptop, run the matching command.

### Dev Laptop

```powershell
cd $env:USERPROFILE\Desktop\AI-Operations-center
git pull
powershell -ExecutionPolicy Bypass -File docker\test-brain-ssh-and-api.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -BrainUser <BrainWindowsUsername> -AgentId programmer
```

### Research Laptop

```powershell
cd $env:USERPROFILE\Desktop\AI-Operations-center
git pull
powershell -ExecutionPolicy Bypass -File docker\test-brain-ssh-and-api.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -BrainUser <BrainWindowsUsername> -AgentId research-lead
```

### Business Laptop

If the repo is not cloned yet:

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/bluejay88/AI-Operations-center.git
cd AI-Operations-center
```

Then run:

```powershell
git pull
powershell -ExecutionPolicy Bypass -File docker\test-brain-ssh-and-api.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -BrainUser <BrainWindowsUsername> -AgentId business-manager
```

## What A Passing Test Means

- `Brain API`: laptop can reach the Brain API.
- `Listener send`: laptop can send work/status back to the Brain.
- `Speaker receive`: laptop can receive instructions, feedback, and approvals from the Brain.
- `SSH to Brain`: laptop can connect to the Brain PC over SSH.

If API/listener/speaker pass but SSH fails, the AI Operations Center can still coordinate through HTTP endpoints, but the Brain cannot use SSH command execution yet.

## Secure Defaults

- SSH is intended for Tailscale only.
- Do not open port 22 to the public internet.
- Use a strong Windows password or SSH keys.
- Keep money, legal, sending, posting, deployment, and file deletion behind Brain/human approval.

