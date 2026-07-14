# Project Intake And Portfolio Audit

Generated: 2026-07-14

## Purpose

Project Intake turns local Codex workspaces, adjacent Desktop projects, and laptop-specific project folders into Brain-visible work packages. The goal is to stop manually hunting through folders and instead let Jayla or a laptop:

1. Select, paste, or drop project paths in the dashboard.
2. Run a local scanner when Docker cannot see host paths.
3. Import a redacted project scan into the Brain API.
4. Route selected projects to Brain, Dev, Research, and Business laptop teams through `/codex/pipeline`.

## New Brain API Contract

- `GET /project-intake/workspaces`: returns detected Codex workspaces plus imported scans.
- `POST /project-intake/audit`: scans selected paths when they are reachable from the Brain process.
- `POST /project-intake/import-scan`: receives scanner output from this PC or any laptop.
- `POST /project-intake/route`: turns selected projects into audited laptop work packages.

## Laptop / Host Scanner

Run from any pulled AI Operations Center repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\scan-projects-to-brain.ps1 -IncludeDesktop -PostToBrain
```

For one specific project:

```powershell
powershell -ExecutionPolicy Bypass -File .\docker\scan-projects-to-brain.ps1 `
  -Roots "C:\Users\jayla\OneDrive\Desktop\Race Aid","C:\Users\jayla\OneDrive\Desktop\Ai Lead Generator" `
  -PostToBrain
```

The scanner reports metadata only: file counts, build files, docs, recent files, and risk flags. It does not print or transmit raw secret values.

## Projects Scanned This Pass

### Race Aid

Evidence reviewed:

- `AI_PROJECT_AUDIT_REPORT.md`
- `AI_COLLAB_BRIDGE_REPORT.md`
- `ai_collab_bridge.py --status`
- `ai_collab_bridge.py --council-report`
- `ai_project_audit_manager.py --max-files 300 --max-books 20`
- Python compile check for bridge, daemon, audit manager, storage, ML worker, runtime smoke, and repair audit scripts.

Results:

- Race Aid bridge is running with local safety constraints.
- Advisory external agents and local RaceAid specialist agents are registered.
- Current bridge status reported `secret_values_printed: false`.
- Bounded audit passed and wrote `output/ai_project_audit.sqlite3`.
- Bounded Race Aid scan sampled 300 files and found 125 TODO/security/placeholder markers, 2 large binary/database items, and 1 large text file.
- Recommendations: reduce monolith/startup/UI choke points, validate leakage-free model improvements, review data/model performance boundaries.

Primary routed work packages:

- Race Aid runtime/UI stabilization and monolith reduction.
- Race Aid model validation and leakage-free promotion plan.
- Race Aid secret hygiene, provider outage handling, and local-only fallback hardening.
- Race Aid data storage/indexing and performance model audit.

### AI Lead Generator / IntentGrid

Evidence reviewed:

- `Real Estate Leads\intentgrid\README.md`
- `docs\security-compliance-checklist.md`
- `docs\business-plan.md`
- `npm run build`
- `npm run audit:ready`
- `npm run crm:contract`
- `npm audit --audit-level=high`

Results:

- Build check passed.
- Readiness audit passed: SMS consent, Fair Housing notice, security header, protected-class scoring absence, consent version, and terms required.
- CRM contract passed: safe wait without `CRM_WEBHOOK_URL`, mock webhook send, consent/routing context, and no protected-class fields.
- `npm audit --audit-level=high` found 0 vulnerabilities.
- Security scan found intentional admin token/password surfaces and documented blocked external secret tasks.

Primary routed work packages:

- IntentGrid production secret/setup gates: `ADMIN_API_TOKEN`, CRM webhook, rate limiting/CAPTCHA, privacy request workflow.
- IntentGrid admin UX polish and security review for session/token handling.
- IntentGrid product growth plan: local SEO pages, lead magnets, first sales sprint, reporting KPI model.
- IntentGrid data model migration plan from Netlify Blobs to a relational CRM/database when reporting needs expand.

### Codex Workspace Metadata

The Codex state contains saved workspaces for AI Operations Center, AI Lead Generator, Race Aid, Comic Generator, Elite Resume Builder, Credit Advisor, Harvard quiz projects, AI Worker, AI Voice Testing, Urban Fighters, Yu-Gi-Oh, and others. It also contains prior Race Aid suggestions covering thought-stream queue repair, Discord runtime health, weather lookup, import coverage, overwrite-safe imports, BrokenProcessPool freeze recovery, SQL index migration, and provider-outage fallback.

## Security Notes

- Project scanner output is redacted metadata, not source content dumps.
- Secret-looking filenames are counted as flags; secret values are not displayed.
- External projects are not edited by the scanner.
- Routing creates dashboard/team-room/operator requests; deployment, credential changes, customer contact, spending, and destructive work remain approval-gated.
