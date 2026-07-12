# Laptop Instruction Deployment

The Brain PC now distributes laptop instructions and AI prompts through GitHub.

## Source Of Truth

- Machine instructions: `instructions/`
- Agent prompts: `prompts/AGENT_PROMPTS.md`
- Factory model for dashboard/API: `config/ai_factory.yaml`
- Agent registry: `config/agents.yaml`
- Machine registry: `config/machines.yaml`

## Update Flow

1. Brain PC edits instructions, prompts, scripts, config, or dashboard.
2. Brain PC commits and pushes to GitHub.
3. Each laptop runs its update command.
4. Worker restarts with the latest repo.
5. Brain dashboard verifies heartbeat, task status, and connectivity.

## Laptop Update Commands

Development laptop:

```powershell
cd $env:USERPROFILE\Desktop\AI-Operations-center
git pull
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32
```

Research laptop:

```powershell
cd $env:USERPROFILE\Desktop\AI-Operations-center
git pull
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId research-laptop -BrainHost 100.70.49.32
```

Business laptop:

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/bluejay88/AI-Operations-center.git
cd AI-Operations-center
powershell -ExecutionPolicy Bypass -File docker\onboard-laptop.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

If the Business laptop already has the repo cloned, use `git pull` and `docker\update-worker-from-git.ps1` instead.

## Verification

Open the dashboard on the Brain PC:

```text
http://localhost:8088/dashboard/
```

Then verify:

- The laptop appears online or recently heartbeating.
- Tailscale ping is online.
- Queued/running/completed task counts update.
- The AI Bridge Factory section lists each laptop's duties, subagents, rubrics, and due windows.
- Business tasks are redistributed if Business Laptop is offline.

