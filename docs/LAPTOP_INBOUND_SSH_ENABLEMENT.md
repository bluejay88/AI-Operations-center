# Laptop Inbound SSH Enablement

This enables the Brain PC to connect into each managed laptop over Tailscale.

Use this only on laptops owned or explicitly managed by Jayla. The safer default remains worker/speaker pull mode. Inbound SSH is for approved administrative actions, diagnostics, and controlled remote operations.

## Security Model

- OpenSSH Server runs on each laptop.
- Windows Firewall allows inbound TCP 22 only from Tailscale CGNAT range `100.64.0.0/10`.
- Brain-to-laptop access uses the dedicated Brain key `ai_ops_brain_to_laptops`.
- Password SSH is disabled by default by `setup-worker-openssh-tailscale-admin.ps1`; use `-AllowPasswordAuthentication` only for temporary break-glass troubleshooting.
- `authorized_keys` permissions are tightened for the laptop user, Administrators, and SYSTEM.
- Admin users also receive the key in `C:\ProgramData\ssh\administrators_authorized_keys` because Windows OpenSSH checks that file for local administrators.
- Sensitive actions still require Brain/Jayla approval.
- Do not open port 22 to public Wi-Fi/LAN broadly.

## Run On Each Laptop As Administrator

Open PowerShell as Administrator inside the repo:

```powershell
cd "$env:USERPROFILE\Desktop\AI-Operations-center"
git pull origin master
powershell -ExecutionPolicy Bypass -File .\docker\setup-worker-openssh-tailscale-admin.ps1
tailscale ip -4
hostname
whoami
```

If `whoami` shows a local username different from `$env:USERNAME`, pass it explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\setup-worker-openssh-tailscale-admin.ps1 -UserName jayla
```

Then run the laptop-specific Business OS configuration:

Dev Laptop:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\configure-laptop-business-os.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32
```

Research Laptop:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\configure-laptop-business-os.ps1 -MachineId research-laptop -BrainHost 100.70.49.32
```

Business Laptop:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\configure-laptop-business-os.ps1 -MachineId business-laptop -BrainHost 100.70.49.32
```

Write down:

- Laptop role: `dev-laptop`, `research-laptop`, or `business-laptop`
- Tailscale IP
- Windows username from `whoami`
- Hostname

## Test From Brain PC

From the Brain PC:

```powershell
ssh <LaptopWindowsUsername>@<LaptopTailscaleIP> hostname
```

Examples:

```powershell
ssh jayla@100.71.82.122 hostname
ssh jayla@100.90.219.88 hostname
ssh jayla@100.112.91.61 hostname
```

Preferred key-based tests:

```powershell
ssh -i "$env:USERPROFILE\.ssh\ai_ops_brain_to_laptops" jayla@100.71.82.122 hostname
ssh -i "$env:USERPROFILE\.ssh\ai_ops_brain_to_laptops" jayla@100.90.219.88 hostname
ssh -i "$env:USERPROFILE\.ssh\ai_ops_brain_to_laptops" jayla@100.112.91.61 hostname
```

The fleet audit uses strict known-host verification and never auto-accepts a
new host key. For `SSH_HOST_KEY_UNVERIFIED`, display the ED25519 fingerprint
locally on that laptop:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\show-laptop-ssh-fingerprint.ps1
```

Compare it out of band with the fingerprint discovered by the Brain. Add the
public host key to the dedicated Brain `known_hosts` file only after an exact
match. A reachable TCP/22 port is not authenticated SSH evidence.

If port 22 is open but key login says `Permission denied`, rerun the setup script on that laptop as Administrator so the Brain public key is installed.

## Start Worker/Speaker Pull Mode

Inbound SSH is optional if the laptop runs the pull worker:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\configure-laptop-business-os.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32
```

Use `research-laptop` or `business-laptop` as appropriate.

## Brain Verification

From Brain PC:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\test-brain-to-laptops.ps1 -LaptopUser <LaptopWindowsUsername>
Invoke-RestMethod http://100.70.49.32:8088/readiness.json
Invoke-RestMethod http://100.70.49.32:8088/security/guardian
```

## Troubleshooting

- If `Test-NetConnection <LaptopIP> -Port 22` fails from Brain, rerun the setup script as Administrator on that laptop.
- If port 22 passes but SSH login fails, the issue is Windows username/password or SSH key authorization.
- Microsoft accounts may not accept `net user` password changes. Use Windows Settings or SSH keys.
- If the laptop is sleeping, SSH will fail; set power settings to keep it awake while working.
