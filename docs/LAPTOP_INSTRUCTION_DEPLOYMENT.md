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
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -ApprovedCommit <approved-commit-sha> -BrainApprovalId <review-id>
```

Research laptop:

```powershell
cd $env:USERPROFILE\Desktop\AI-Operations-center
powershell -ExecutionPolicy Bypass -File docker\update-worker-from-git.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -ApprovedCommit <approved-commit-sha> -BrainApprovalId <review-id>
```

Business laptop:

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/bluejay88/AI-Operations-center.git
cd AI-Operations-center
powershell -ExecutionPolicy Bypass -File docker\onboard-laptop.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -RenameTailscale
```

If the Business laptop already has the repo cloned, use the approval-pinned `docker\update-worker-from-git.ps1` command instead of pulling directly.

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

## Laptop Status Semantics

Laptop status has two independent dimensions. `workforce_status` comes from
`config/machines.yaml` and answers whether a laptop is assigned to the workforce.
Live `runtime_state` comes from heartbeats and connectivity scans and answers what
the Brain can currently observe.

An **active laptop** must be both `workforce_status: employed` and
`runtime_state: online`. Tailscale reachability by itself does not make a laptop
active: a reachable laptop with no fresh worker heartbeat is
`reachable_not_onboarded` or `reachable_worker_stale`. Likewise, an employed
laptop may be offline without losing its workforce assignment.

The expected live cadence is:

- Worker heartbeat every 10 seconds.
- Tailscale/SSH connectivity scan every 30 seconds.
- Worker status becomes stale after 60 seconds without a heartbeat.

Every status response should include its observation time (`last_seen` or the
scan timestamp). UI and automation should use runtime state for task routing and
`workforce_status` for inventory or staffing counts.
