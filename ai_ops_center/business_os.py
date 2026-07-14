from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .brain_bus import create_speaker_message, submit_listener_event
from .db import connect
from .github_defaults import github_defaults_dict
from .orchestrator import create_task


ZERO_BUDGET_GOAL = {
    "owner": "Jayla",
    "starting_budget": 0.00,
    "currency": "USD",
    "monthly_target": 25000,
    "target_type": "5-6 figure monthly revenue target",
    "rule": "Do not represent income as guaranteed. Use evidence gates before scaling.",
}


APPROVAL_MATRIX = [
    ("ordinary_faq", "automated", "Answer from approved policy only; log response."),
    ("order_status", "automated", "Use verified order records; no private data leakage."),
    ("first_draft_deliverable", "automated_after_intake", "Create draft and send to QA, not directly to customer unless approved product policy allows it."),
    ("low_risk_delivery", "qa_threshold", "Allowed only after QA score and scope checks pass."),
    ("scheduled_social_from_approved_queue", "automated", "Only publish items already approved by Jayla/Brain policy."),
    ("price_test_copy", "approval_required", "Can draft variants; Brain/Jayla approve public change."),
    ("increase_ad_spend", "human_required", "Jayla approval required above $0; no new spend by default."),
    ("refund_under_25", "policy_gate", "Allowed only after clear policy match and fraud check."),
    ("refund_over_25", "human_required", "Jayla approval required."),
    ("contract_signature", "human_only", "AI may draft and summarize only."),
    ("tax_filing", "human_only", "AI may prepare checklists only."),
    ("bank_account_change", "human_only", "AI must never change banking destinations."),
    ("permanent_data_delete", "human_required", "Soft-delete by default; permanent delete requires explicit approval."),
    ("legal_threat_response", "human_or_legal_required", "Escalate immediately."),
    ("security_breach", "human_required_immediate", "Pause external actions and escalate."),
]


BUSINESS_PHASES = [
    ("idea", "Define problem, customer, why now, value proposition, one-sentence pitch, founder story.", "business-manager", "business-laptop", 95),
    ("market_research", "Research TAM/SAM/SOM, trends, customer pain, competitors, reviews, pricing, regulations.", "market-intelligence", "research-laptop", 94),
    ("business_model", "Define revenue streams, unit economics, target price, upsells, subscriptions, and margin assumptions.", "finance-manager", "business-laptop", 92),
    ("business_plan", "Create executive summary, operations, marketing, sales, management, risks, growth plan.", "business-manager", "business-laptop", 91),
    ("financial_model", "Create 30/60/90-day and 5-year assumptions, break-even, cash-flow, best/expected/worst cases.", "finance-auditor", "brain-gaming-pc", 90),
    ("pitch_package", "Draft investor-style one-page overview, pitch deck outline, and data-room checklist.", "business-manager", "business-laptop", 84),
    ("marketing_plan", "Create brand voice, SEO, content calendar, email sequence, outreach, referral and partnership plan.", "marketing-agent", "business-laptop", 91),
    ("sales_plan", "Define lead generation, CRM fields, qualification, pricing, follow-up, retention, upsell path.", "lead-generation", "business-laptop", 92),
    ("product_development", "Create product scope, templates, intake, QA rubric, delivery format, roadmap, and security requirements.", "digital-products", "brain-gaming-pc", 90),
    ("website_package", "Create landing page, offer copy, FAQ, checkout/intake notes, analytics and private deployment checklist.", "website-builder", "dev-laptop", 89),
    ("operations", "Create SOPs, customer support scripts, fulfillment workflow, escalation rules, and report cadence.", "customer-success", "business-laptop", 88),
    ("legal_review_packet", "Prepare LLC/legal/tax/privacy/terms checklist for Jayla or qualified professional review.", "business-manager", "business-laptop", 86),
    ("risk_analysis", "Create risk register and mitigation plans for market, finance, legal, tech, cybersecurity, operations.", "security-monitor", "brain-gaming-pc", 90),
    ("funding_strategy", "Find grants, SBA/local programs, non-dilutive funding, and data-room requirements.", "grant-scout", "research-laptop", 88),
    ("growth_strategy", "Define expansion, automation, partnerships, subscriptions, and success gates for scaling.", "orchestrator", "brain-gaming-pc", 87),
    ("metrics", "Define KPIs: revenue, MRR, CAC, LTV, margin, conversion, retention, refunds, support defects.", "project-coordinator", "brain-gaming-pc", 89),
    ("launch_assets", "Create demo, sample deliverable, support center, FAQs, case-study template, and press kit checklist.", "content-engine", "brain-gaming-pc", 86),
    ("qa_and_approval", "Run dual-agent review, deterministic checks, approval matrix, launch gate, rollback and kill-switch plan.", "rubric-auditor", "brain-gaming-pc", 95),
]


ZERO_BUDGET_BUSINESSES = [
    {
        "id": "ai-website-maintenance",
        "name": "AI Website Maintenance Studio",
        "offer": "Monthly website updates, analytics, uptime checks, SEO refreshes, and AI content support.",
        "audience": "Local small businesses with outdated websites.",
        "first_sale_path": "Manual outreach and free audit report; no paid ads until conversion proof.",
        "starter_price": 299,
        "recurring_price": 499,
    },
    {
        "id": "grant-readiness-briefs",
        "name": "Grant Readiness Briefs",
        "offer": "Grant opportunity lists, eligibility summaries, document checklists, and draft narratives.",
        "audience": "Illinois small businesses, nonprofits, workforce programs, and local founders.",
        "first_sale_path": "Research public grant deadlines and offer a paid readiness brief.",
        "starter_price": 149,
        "recurring_price": 299,
    },
    {
        "id": "digital-ops-template-shop",
        "name": "Digital Operations Template Shop",
        "offer": "Business forms, SOP packs, prompt libraries, planners, checklists, and spreadsheet calculators.",
        "audience": "Solo founders, creators, job seekers, and small business operators.",
        "first_sale_path": "Launch one high-quality bundle and collect feedback before building a catalog.",
        "starter_price": 29,
        "recurring_price": 0,
    },
    {
        "id": "local-lead-gen-kits",
        "name": "Local Lead Generation Kits",
        "offer": "Niche prospect lists, outreach scripts, landing page copy, CRM columns, and follow-up plans.",
        "audience": "Service providers who need clients but lack a sales system.",
        "first_sale_path": "Build sample kit for one niche, sell via direct outreach and partnerships.",
        "starter_price": 199,
        "recurring_price": 399,
    },
    {
        "id": "ai-content-retainer",
        "name": "AI Content Retainer",
        "offer": "Monthly blog, Shorts, LinkedIn, TikTok, email, and repurposing calendar package.",
        "audience": "Small businesses that need consistent content without hiring staff.",
        "first_sale_path": "Create sample month for one niche and pitch content consistency problem.",
        "starter_price": 399,
        "recurring_price": 799,
    },
]


LAPTOP_SETUP_PACKETS = {
    "brain-gaming-pc": {
        "agent": "orchestrator",
        "role": "Brain Orchestrator / CEO",
        "commands": [
            "cd \"C:\\Users\\jayla\\OneDrive\\Desktop\\Ai Operations Center\"",
            "git pull origin master",
            "docker compose up -d --build ai-ops-api",
            "Invoke-RestMethod http://100.70.49.32:8088/health",
            "Invoke-RestMethod http://100.70.49.32:8088/security/guardian",
            "Invoke-RestMethod -Method Post http://100.70.49.32:8088/business-os/seed",
        ],
    },
    "dev-laptop": {
        "agent": "programmer",
        "role": "Lead Software Engineer",
        "commands": [
            "cd $env:USERPROFILE\\Desktop\\AI-Operations-center",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\update-worker-from-git.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -ApprovedCommit APPROVED_COMMIT_SHA -BrainApprovalId APPROVAL_ID",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\test-brain-ssh-and-api.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32 -BrainUser aiopsbrain -AgentId programmer",
            "powershell -ExecutionPolicy Bypass -File .\\laptop_packages\\dev-laptop\\install.ps1 -BrainHost 100.70.49.32",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\start-laptop-operations.ps1 -MachineId dev-laptop -BrainHost 100.70.49.32",
        ],
    },
    "research-laptop": {
        "agent": "research-lead",
        "role": "Research Intelligence",
        "commands": [
            "cd $env:USERPROFILE\\Desktop\\AI-Operations-center",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\update-worker-from-git.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -ApprovedCommit APPROVED_COMMIT_SHA -BrainApprovalId APPROVAL_ID",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\test-brain-ssh-and-api.ps1 -MachineId research-laptop -BrainHost 100.70.49.32 -BrainUser aiopsbrain -AgentId research-lead",
            "powershell -ExecutionPolicy Bypass -File .\\laptop_packages\\research-laptop\\install.ps1 -BrainHost 100.70.49.32",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\start-laptop-operations.ps1 -MachineId research-laptop -BrainHost 100.70.49.32",
        ],
    },
    "business-laptop": {
        "agent": "business-manager",
        "role": "Business Operations",
        "commands": [
            "cd $env:USERPROFILE\\Desktop\\AI-Operations-center",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\update-worker-from-git.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -ApprovedCommit APPROVED_COMMIT_SHA -BrainApprovalId APPROVAL_ID",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\test-brain-ssh-and-api.ps1 -MachineId business-laptop -BrainHost 100.70.49.32 -BrainUser aiopsbrain -AgentId business-manager",
            "powershell -ExecutionPolicy Bypass -File .\\laptop_packages\\business-laptop\\install.ps1 -BrainHost 100.70.49.32",
            "powershell -ExecutionPolicy Bypass -File .\\docker\\start-laptop-operations.ps1 -MachineId business-laptop -BrainHost 100.70.49.32",
        ],
    },
}

ENTERPRISE_DEPARTMENTS = [
    {
        "id": "executive-office",
        "name": "Executive Office",
        "machine": "brain-gaming-pc",
        "agents": [
            ("chief-executive-ai", "Chief Executive AI", "Company strategy, goal prioritization, resource allocation, final decision support, portfolio management, and executive summaries."),
            ("chief-operating-officer-ai", "Chief Operating Officer AI", "Daily operations, workflow optimization, bottleneck detection, process improvement, team coordination, and capacity planning."),
            ("chief-financial-officer-ai", "Chief Financial Officer AI", "Financial modeling, budgets, cash flow forecasts, pricing analysis, revenue projections, scenarios, KPI dashboards, and profitability analysis."),
            ("chief-technology-officer-ai", "Chief Technology Officer AI", "Software architecture, technology selection, infrastructure planning, AI model selection, security reviews, and technical roadmaps."),
        ],
    },
    {
        "id": "project-management-office",
        "name": "Project Management Office",
        "machine": "brain-gaming-pc",
        "agents": [
            ("program-manager-ai", "Program Manager AI", "Master roadmap, portfolio planning, milestones, dependencies, and cross-project reporting."),
            ("project-manager-ai", "Project Manager AI", "Sprint planning, requirements, user stories, acceptance criteria, scheduling, team assignments, and daily reporting."),
            ("scrum-master-ai", "Scrum Master AI", "Sprint health, standups, burndown, blockers, and team operating rhythm."),
            ("business-analyst-ai", "Business Analyst AI", "Requirements gathering, process mapping, documentation, workflow design, and stakeholder translation."),
        ],
    },
    {
        "id": "customer-success-division",
        "name": "Customer Success Division",
        "machine": "business-laptop",
        "agents": [
            ("customer-support-agent-ai", "Customer Support Agent AI", "Live chat drafts, email drafts, FAQ generation, ticket categorization, knowledge-base suggestions, and escalations."),
            ("customer-success-manager-ai", "Customer Success Manager AI", "Customer onboarding, adoption, satisfaction metrics, renewal reminders, and retention analysis."),
            ("community-manager-ai", "Community Manager AI", "Discord, Reddit, Facebook Groups, community moderation drafts, and feedback summaries."),
            ("voice-of-customer-ai", "Voice of Customer AI", "Reviews, feature requests, support tickets, surveys, sentiment, and recommendations for Product."),
        ],
    },
    {
        "id": "business-creation-division",
        "name": "Business Creation Division",
        "machine": "brain-gaming-pc",
        "agents": [
            ("business-creator-ai", "Business Creator AI", "Executive summary, company description, vision, mission, values, SWOT, TAM/SAM/SOM, pricing, revenue model, plans, forecasts, KPIs, and launch timeline."),
        ],
    },
    {
        "id": "investor-readiness-division",
        "name": "Investor Readiness Division",
        "machine": "brain-gaming-pc",
        "agents": [
            ("investor-readiness-ai", "Investor Readiness AI", "Pitch deck, one-pager, executive summary, financial model, cap table placeholder, investment memo, data room, risk assessment, growth strategy, and investor Q&A drafts."),
        ],
    },
    {
        "id": "product-division",
        "name": "Product Division",
        "machine": "dev-laptop",
        "agents": [
            ("product-manager-ai", "Product Manager AI", "Product roadmap, specifications, user personas, customer journeys, prioritization, UX recommendations, pricing, release plans, and beta programs."),
        ],
    },
    {
        "id": "engineering-division",
        "name": "Engineering Division",
        "machine": "dev-laptop",
        "agents": [
            ("frontend-engineer-ai", "Frontend Engineer AI", "Frontend architecture, UI implementation, accessibility, tests, and documentation."),
            ("backend-engineer-ai", "Backend Engineer AI", "Backend services, APIs, database integration, reliability, tests, and documentation."),
            ("devops-engineer-ai", "DevOps Engineer AI", "CI/CD, Docker, deployment checks, rollback plans, monitoring, and release readiness."),
        ],
    },
    {
        "id": "research-division",
        "name": "Research Division",
        "machine": "research-laptop",
        "agents": [
            ("academic-research-ai", "Academic Research AI", "Academic research, source scoring, evidence synthesis, and citation-backed briefs."),
            ("patent-scout-ai", "Patent Scout AI", "Patent searches, IP landscape summaries, and technology defensibility notes."),
            ("regulatory-watch-ai", "Regulatory Watch AI", "Regulatory updates, compliance risk summaries, and escalation recommendations."),
        ],
    },
    {
        "id": "quality-assurance-division",
        "name": "Quality Assurance Division",
        "machine": "dev-laptop",
        "agents": [
            ("quality-director-ai", "Quality Director AI", "Scores deliverables for completeness, accuracy, consistency, readability, security, maintainability, and business alignment."),
        ],
    },
    {
        "id": "marketing-division",
        "name": "Marketing Division",
        "machine": "business-laptop",
        "agents": [
            ("brand-strategist-ai", "Brand Strategist AI", "Brand identity, positioning, messaging, audience clarity, offer framing, and approved voice guidelines."),
            ("content-engine-ai", "Content Engine AI", "Blog drafts, short-form video scripts, social posts, email newsletters, repurposing plans, and content calendars."),
            ("seo-growth-ai", "SEO Growth AI", "Keyword research, search intent mapping, metadata, internal linking, content gaps, and organic conversion recommendations."),
        ],
    },
    {
        "id": "sales-division",
        "name": "Sales Division",
        "machine": "business-laptop",
        "agents": [
            ("prospecting-ai", "Prospecting AI", "Lead source discovery, qualification criteria, niche lists, outreach research, and CRM-ready prospect records."),
            ("sales-playbook-ai", "Sales Playbook AI", "Sales scripts, objection handling, proposal drafts, follow-up sequences, and close-readiness checklists."),
            ("partnership-ai", "Partnership AI", "Affiliate, referral, reseller, and local partner discovery with outreach drafts and relationship tracking."),
        ],
    },
    {
        "id": "finance-division",
        "name": "Finance Division",
        "machine": "brain-gaming-pc",
        "agents": [
            ("finance-operations-ai", "Finance Operations AI", "Transaction categorization drafts, invoice summaries, cash-flow snapshots, failed-payment tracking, and tax-reserve reminders."),
            ("unit-economics-ai", "Unit Economics AI", "Contribution margin, CAC, LTV, break-even, pricing sensitivity, refund impact, and scale-readiness calculations."),
            ("funding-strategy-ai", "Funding Strategy AI", "Grant, SBA, local funding, revenue-based financing, and investor-readiness options with eligibility notes."),
        ],
    },
    {
        "id": "legal-compliance",
        "name": "Legal & Compliance",
        "machine": "brain-gaming-pc",
        "agents": [
            ("compliance-officer-ai", "Compliance Officer AI", "Privacy, terms, refund policy, disclosure, regulated-claim, and customer-data handling checklists for human review."),
            ("contract-review-ai", "Contract Review AI", "Contract summaries, risk flags, missing terms, obligation trackers, and questions for Jayla or qualified counsel."),
            ("policy-steward-ai", "Policy Steward AI", "Approval matrix maintenance, data-retention rules, escalation logic, and SOP policy versioning."),
        ],
    },
    {
        "id": "operations-division",
        "name": "Operations Division",
        "machine": "brain-gaming-pc",
        "agents": [
            ("workflow-ops-ai", "Workflow Operations AI", "SOPs, workflow diagrams, queue hygiene, bottleneck reviews, automation handoffs, and recovery procedures."),
            ("fulfillment-ops-ai", "Fulfillment Operations AI", "Intake validation, production routing, delivery checklists, revision handling, and deadline monitoring."),
            ("vendor-tools-ai", "Vendor & Tools AI", "Software inventory, vendor register, account-change checklists, renewal reminders, and tool fit analysis."),
        ],
    },
    {
        "id": "human-resources",
        "name": "Human Resources",
        "machine": "business-laptop",
        "agents": [
            ("people-ops-ai", "People Operations AI", "Role definitions, hiring plans, onboarding checklists, performance rubrics, and contractor coordination drafts."),
            ("training-ai", "Training AI", "Internal guides, training paths, SOP explanations, skill matrices, and quiz/checklist generation."),
        ],
    },
    {
        "id": "security-operations",
        "name": "Security Operations",
        "machine": "brain-gaming-pc",
        "agents": [
            ("shield-soc-ai", "Shield SOC AI", "SSH trust validation, device posture checks, alert triage, security event summaries, and incident escalation."),
            ("access-review-ai", "Access Review AI", "Least-privilege reviews, key rotation checklists, account inventory, and sensitive-action approval checks."),
            ("backup-recovery-ai", "Backup & Recovery AI", "Backup verification, restore drills, low-battery save rules, Git checkpointing, and continuity handoffs."),
        ],
    },
    {
        "id": "business-intelligence",
        "name": "Business Intelligence",
        "machine": "brain-gaming-pc",
        "agents": [
            ("kpi-analyst-ai", "KPI Analyst AI", "Revenue, MRR, leads, conversion, workload, cycle time, quality, and operational dashboard metrics."),
            ("reporting-analyst-ai", "Reporting Analyst AI", "Daily, weekly, monthly, quarterly reports, spreadsheet exports, executive briefs, and variance explanations."),
            ("experiment-analyst-ai", "Experiment Analyst AI", "Experiment design, success metrics, guardrails, result summaries, and scale/stop recommendations."),
        ],
    },
    {
        "id": "innovation-lab",
        "name": "Innovation Lab",
        "machine": "research-laptop",
        "agents": [
            ("innovation-lab-ai", "Innovation Lab AI", "New business ideas, product concepts, AI workflow improvements, emerging technologies, and experimental prototypes."),
        ],
    },
]


def seed_autonomous_business_os(local: bool = False) -> dict[str, Any]:
    created_projects = 0
    created_tasks = 0
    created_notes = 0
    speaker_messages = 0
    defaults = github_defaults_dict()
    now = datetime.now(UTC).isoformat()

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            _ensure_base_project(cur)
            for business in ZERO_BUDGET_BUSINESSES:
                project_id = f"business-{business['id']}"
                cur.execute(
                    """
                    insert into projects (
                        id, name, project_type, status, current_owner_agent_id, current_owner_machine_id,
                        progress, risk_score, cost_estimate, quality_score, test_coverage, revenue_target,
                        goals, metadata
                    )
                    values (%s, %s, 'autonomous_business', 'planning', 'orchestrator', 'brain-gaming-pc',
                        5, 42, 0, 70, 0, %s, %s::jsonb, %s::jsonb)
                    on conflict (id) do update set
                        name = excluded.name,
                        status = excluded.status,
                        revenue_target = excluded.revenue_target,
                        goals = excluded.goals,
                        metadata = excluded.metadata,
                        updated_at = now()
                    returning (xmax = 0) as inserted
                    """,
                    (
                        project_id,
                        business["name"],
                        ZERO_BUDGET_GOAL["monthly_target"],
                        _json(
                            [
                                "Validate demand in 30-60 days",
                                "Start with $0 paid spend",
                                "Require Jayla approval for banking, legal, spending, public sends, contracts, and irreversible actions",
                                "Build toward $25,000/month through profitable, repeatable offers",
                            ]
                        ),
                        _json({**business, "goal": ZERO_BUDGET_GOAL, "github": defaults, "seeded_at": now}),
                    ),
                )
                if cur.fetchone()["inserted"]:
                    created_projects += 1

                created_notes += _insert_business_notes(cur, project_id, business)

                for phase, description, agent_id, machine_id, priority in BUSINESS_PHASES:
                    category = phase
                    dedupe_key = f"{project_id}:{phase}:business-os-v1"
                    cur.execute(
                        """
                        insert into tasks (title, agent_id, category, description, priority, metadata)
                        select %s, %s, %s, %s, %s, %s::jsonb
                        where not exists (select 1 from tasks where metadata->>'dedupe_key' = %s)
                        returning id
                        """,
                        (
                            f"{business['name']} - {phase.replace('_', ' ').title()}",
                            agent_id,
                            category,
                            _business_task_description(business, phase, description),
                            priority,
                            _json(
                                {
                                    "dedupe_key": dedupe_key,
                                    "project_id": project_id,
                                    "business_id": business["id"],
                                    "target_machine_id": machine_id,
                                    "approval_matrix": APPROVAL_MATRIX,
                                    "zero_budget_goal": ZERO_BUDGET_GOAL,
                                    "created_by": "autonomous_business_os",
                                }
                            ),
                            dedupe_key,
                        ),
                    )
                    if cur.fetchone():
                        created_tasks += 1

            cur.execute(
                """
                insert into prompts (name, owner_agent_id, purpose, prompt_text, version, status, metadata)
                values (%s, 'orchestrator', 'autonomous business operating prompt', %s, 1, 'active', %s::jsonb)
                on conflict (name, version) do update set
                    prompt_text = excluded.prompt_text,
                    metadata = excluded.metadata,
                    updated_at = now()
                """,
                ("autonomous_business_os_master_prompt", autonomous_business_prompt(), _json({"approval_matrix": APPROVAL_MATRIX})),
            )
            cur.execute(
                """
                insert into prompts (name, owner_agent_id, purpose, prompt_text, version, status, metadata)
                values (%s, 'orchestrator', 'brain orchestrator device control prompt', %s, 1, 'active', %s::jsonb)
                on conflict (name, version) do update set
                    prompt_text = excluded.prompt_text,
                    metadata = excluded.metadata,
                    updated_at = now()
                """,
                ("brain_orchestrator_device_control_prompt", brain_orchestrator_prompt(), _json({"source": "user-approved-operating-role"})),
            )
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'seed_autonomous_business_os', 'business_os', 'zero-budget-launch', %s, %s::jsonb)
                """,
                (
                    f"Seeded autonomous business OS: {created_projects} projects, {created_tasks} tasks, {created_notes} notes.",
                    _json({"goal": ZERO_BUDGET_GOAL, "business_count": len(ZERO_BUDGET_BUSINESSES)}),
                ),
            )
        conn.commit()

    for machine_id in LAPTOP_SETUP_PACKETS:
        create_speaker_message(
            target_id=machine_id,
            message_type="business_os_setup",
            subject=f"{machine_id} Business OS setup checklist",
            body=laptop_setup_prompt(machine_id),
            priority=94,
            metadata={"machine_id": machine_id, "source": "autonomous_business_os", "commands": LAPTOP_SETUP_PACKETS[machine_id]["commands"]},
            local=local,
        )
        speaker_messages += 1

    event = submit_listener_event(
        source_type="business_os",
        source_id="autonomous-business-os",
        event_type="workload_update",
        subject="Autonomous Business OS seeded",
        body=f"Created/updated {len(ZERO_BUDGET_BUSINESSES)} zero-budget business launch pipelines with approval gates for Jayla.",
        priority=96,
        metadata={"created_projects": created_projects, "created_tasks": created_tasks, "speaker_messages": speaker_messages, "goal": ZERO_BUDGET_GOAL},
        local=local,
    )
    return {
        "businesses": len(ZERO_BUDGET_BUSINESSES),
        "created_projects": created_projects,
        "created_tasks": created_tasks,
        "created_notes": created_notes,
        "speaker_messages": speaker_messages,
        "listener_event_id": event.get("event_id"),
        "goal": ZERO_BUDGET_GOAL,
    }


def seed_enterprise_departments(local: bool = False) -> dict[str, Any]:
    created_agents = 0
    updated_agents = 0
    created_prompts = 0
    created_tasks = 0
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            _ensure_base_project(cur)
            for department in ENTERPRISE_DEPARTMENTS:
                cur.execute(
                    """
                    insert into project_notes (project_id, note_type, title, body, source, metadata)
                    select 'ai-operations-center-2', 'department', %s, %s, 'enterprise-org-seed', %s::jsonb
                    where not exists (
                        select 1 from project_notes
                        where project_id = 'ai-operations-center-2' and note_type = 'department' and title = %s
                    )
                    """,
                    (department["name"], department_prompt(department), _json({"department_id": department["id"]}), department["name"]),
                )
                for agent_id, name, mission in department["agents"]:
                    cur.execute(
                        """
                        insert into agents (id, name, machine_id, category, mission, cadence, tools, guardrails, status)
                        values (%s, %s, %s, %s, %s, 'daily', %s::jsonb, %s::jsonb, 'active')
                        on conflict (id) do update set
                            name = excluded.name,
                            machine_id = excluded.machine_id,
                            category = excluded.category,
                            mission = excluded.mission,
                            tools = excluded.tools,
                            guardrails = excluded.guardrails,
                            status = 'active',
                            updated_at = now()
                        returning (xmax = 0) as inserted
                        """,
                        (
                            agent_id,
                            name,
                            department["machine"],
                            department["id"],
                            mission,
                            _json(["brain-api", "postgres", "speaker-feed", "listener-events", "model-router", "github"]),
                            _json(["jayla-approval-for-money", "jayla-approval-for-legal", "jayla-approval-for-public-sends", "least-privilege"]),
                        ),
                    )
                    if cur.fetchone()["inserted"]:
                        created_agents += 1
                    else:
                        updated_agents += 1

                    cur.execute(
                        """
                        insert into prompts (name, owner_agent_id, purpose, prompt_text, version, status, metadata)
                        values (%s, %s, 'department agent system prompt', %s, 1, 'active', %s::jsonb)
                        on conflict (name, version) do update set
                            owner_agent_id = excluded.owner_agent_id,
                            prompt_text = excluded.prompt_text,
                            metadata = excluded.metadata,
                            updated_at = now()
                        returning id
                        """,
                        (
                            f"department_prompt_{agent_id}",
                            agent_id,
                            agent_system_prompt(department["name"], name, mission),
                            _json({"department_id": department["id"], "machine_id": department["machine"]}),
                        ),
                    )
                    if cur.fetchone():
                        created_prompts += 1

                    dedupe_key = f"enterprise-org:{agent_id}:standing-brief"
                    cur.execute(
                        """
                        insert into tasks (title, agent_id, category, description, priority, metadata)
                        select %s, %s, %s, %s, 72, %s::jsonb
                        where not exists (select 1 from tasks where metadata->>'dedupe_key' = %s)
                        returning id
                        """,
                        (
                            f"Standing brief - {name}",
                            agent_id,
                            department["id"],
                            f"Create the first operating brief for {name}. Include responsibilities, recurring outputs, KPIs, escalation rules, laptop dependencies, and first 3 useful tasks.",
                            _json({"dedupe_key": dedupe_key, "department_id": department["id"], "created_by": "enterprise_org_seed"}),
                            dedupe_key,
                        ),
                    )
                    if cur.fetchone():
                        created_tasks += 1
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'seed_enterprise_departments', 'enterprise_org', 'ceo-brain', %s, %s::jsonb)
                """,
                (
                    f"Seeded enterprise departments: {created_agents} agents created, {updated_agents} updated, {created_tasks} standing briefs.",
                    _json({"departments": [d["id"] for d in ENTERPRISE_DEPARTMENTS]}),
                ),
            )
        conn.commit()
    return {"departments": len(ENTERPRISE_DEPARTMENTS), "created_agents": created_agents, "updated_agents": updated_agents, "created_prompts": created_prompts, "created_tasks": created_tasks}


def enterprise_org_snapshot(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select category as department_id, count(*) as active_agents
                from agents
                where status = 'active'
                group by category
                order by category
                """
            )
            counts = [dict(row) for row in cur.fetchall()]
    return {"ceo": "CEO / BRAIN", "departments": ENTERPRISE_DEPARTMENTS, "active_agent_counts": counts}


def department_prompt(department: dict[str, Any]) -> str:
    agent_lines = "\n".join(f"- {name}: {mission}" for _, name, mission in department["agents"])
    return (
        f"Department: {department['name']}\n"
        f"Primary machine: {department['machine']}\n"
        "Agents:\n"
        f"{agent_lines}\n\n"
        "Operating rules: use Brain API as source of truth, publish progress to listener/events, pull commands from speaker/feed, and require Jayla approval for money, legal, banking, public sending, account changes, contracts, and destructive actions."
    )


def agent_system_prompt(department_name: str, agent_name: str, mission: str) -> str:
    return (
        f"ROLE: {agent_name} in the {department_name} of Jayla's Bleujay AI Operations Center.\n"
        f"MISSION: {mission}\n"
        "GOAL: produce useful, evidence-backed work that increases productivity, protects the operation, or advances approved revenue pipelines.\n"
        "TOOLS: Brain API, task queue, project notes, model-router, GitHub repo instructions, listener/speaker bus, approved external workflows.\n"
        "PROHIBITED WITHOUT APPROVAL: spending money, sending customer messages, publishing publicly, filing legal/tax documents, changing accounts, banking, contracts, destructive changes, credential changes.\n"
        "OUTPUT: status, evidence, deliverables, risks, confidence, approval needs, next actions, due date, and handoff notes.\n"
        "LOGGING: every meaningful action must be reported to the Brain listener or stored in project notes/work logs."
    )


def business_os_snapshot(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                """
                select id, name, status, progress, risk_score, quality_score, revenue_target, goals, metadata, updated_at
                from projects
                where project_type = 'autonomous_business'
                order by updated_at desc, id
                """
            )
            businesses = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                select t.status, count(*) as count
                from tasks t
                where t.metadata->>'created_by' = 'autonomous_business_os'
                group by t.status
                order by t.status
                """
            )
            task_counts = [dict(row) for row in cur.fetchall()]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "goal": ZERO_BUDGET_GOAL,
        "approval_matrix": APPROVAL_MATRIX,
        "businesses": businesses,
        "task_counts": task_counts,
        "laptop_setup": LAPTOP_SETUP_PACKETS,
    }


def laptop_setup_prompt(machine_id: str) -> str:
    packet = LAPTOP_SETUP_PACKETS[machine_id]
    commands = "\n".join(packet["commands"])
    return (
        f"You are the {packet['role']} laptop for Jayla's Bleujay AI Operations Center.\n\n"
        f"Repo: {github_defaults_dict()['remote_url']}\n"
        "Brain API: http://100.70.49.32:8088\n"
        "Dashboard: http://100.70.49.32:8088/dashboard/\n\n"
        "Run these PowerShell commands in order:\n"
        f"{commands}\n\n"
        "Then report status with:\n"
        f"Invoke-RestMethod -Method Post http://100.70.49.32:8088/listener/events -ContentType 'application/json' -Body '{{\"source_type\":\"machine\",\"source_id\":\"{machine_id}\",\"event_type\":\"workload_update\",\"subject\":\"{machine_id} setup complete\",\"body\":\"Pulled GitHub, opened the AI Ops Node Console, tested Brain API, and started laptop operations.\",\"priority\":90,\"metadata\":{{\"machine_id\":\"{machine_id}\",\"agent_id\":\"{packet['agent']}\"}}}}'\n\n"
        "Rules: no spending, public publishing, customer sends, account changes, contracts, banking, legal filings, or destructive operations without Brain/Jayla approval."
    )


def autonomous_business_prompt() -> str:
    return (
        "ROLE: Autonomous Business OS agent for Jayla's private AI Operations Center.\n"
        "GOAL: Research, create, validate, and operate approved online business pipelines toward a $25,000/month target from a $0 starting budget.\n"
        "ALLOWED: research, draft, build mockups, create templates, create tasks, produce reports, update database records, propose offers, prepare customer-service drafts.\n"
        "PROHIBITED WITHOUT JAYLA APPROVAL: spending money, banking, legal filings, contracts, sending customer messages, publishing public claims, deploying client-facing paid offers, deleting records, changing accounts.\n"
        "SOURCE OF TRUTH: Brain API, PostgreSQL, GitHub repo, prompts, approval matrix, task queue, speaker/listener bus.\n"
        "DECISION RULES: start with one audience and one narrow offer; require demand evidence; scale only if contribution margin is positive and support/refund risk is controlled.\n"
        "OUTPUT: structured work product with owner, evidence, assumptions, deliverables, risks, approval needs, tests, next actions, and due date.\n"
        "QUALITY: creator and critic must be different agents; deterministic calculations must be checked by code or spreadsheet logic; all actions must be logged."
    )


def brain_orchestrator_prompt() -> str:
    return (
        "ROLE: Brain Orchestrator for Jayla's private AI Operations Center.\n"
        "AUTHORITY: Coordinate only registered, authenticated, encrypted, owned or explicitly managed devices.\n"
        "CORE RESPONSIBILITIES: executive decision engine, project manager, infrastructure manager, AI coordinator, resource scheduler, performance optimizer, system health monitor, and security coordinator.\n"
        "DEVICE MANAGEMENT: maintain live registry and telemetry for device name, hostname, OS, CPU, GPU, RAM, storage, battery, user, network, Tailscale, models, active projects, tasks, idle, temperature, load, and health score.\n"
        "REMOTE MANAGEMENT: request approved operations such as opening approved apps, restarting services, launching dev environments, Git pull/push, tests, builds, deployments, file sync, and approved workflows.\n"
        "SECURITY: never execute destructive or high-impact operations without authorization; require approval outside pre-approved policies; keep complete audit logs.\n"
        "TASK ROUTING: evaluate CPU, GPU, RAM, workload, priority, deadlines, capability, battery, network, and estimated completion; assign work to the best available machine and rebalance when conditions change.\n"
        "COLLABORATION: every workstation publishes progress, logs, metrics, errors, recommendations, and ETA through listener/events; Brain sends commands through speaker/feed.\n"
        "DASHBOARD: maintain real-time status for devices, agents, projects, queue, health, latency, builds, deployments, AI use, resources, notifications, reports, and KPIs.\n"
        "LOGGING: every action records timestamp, device, agent, user, project, task, duration, outcome, and resource consumption.\n"
        "GUIDING PRINCIPLES: reliability, security, transparency, efficient collaboration, human oversight for sensitive actions, and continuous improvement from historical performance."
    )


def _ensure_schema(cur: Any) -> None:
    cur.execute("alter table projects add column if not exists revenue_target numeric(14, 2)")
    cur.execute(
        """
        create table if not exists business_decision_records (
            id bigserial primary key,
            project_id text references projects(id) on delete cascade,
            decision text not null,
            current_situation text not null,
            evidence jsonb not null default '[]',
            options jsonb not null default '[]',
            expected_benefit text,
            expected_cost text,
            risk_level text not null default 'medium',
            reversibility text not null default 'reversible',
            confidence numeric(5, 2) not null default 0.50,
            authority_required text not null default 'brain_review',
            selected_action text,
            success_metric text,
            review_date date,
            metadata jsonb not null default '{}',
            created_at timestamptz not null default now()
        )
        """
    )


def _ensure_base_project(cur: Any) -> None:
    cur.execute("alter table projects add column if not exists revenue_target numeric(14, 2)")
    cur.execute(
        """
        insert into projects (
            id, name, project_type, status, current_owner_agent_id, current_owner_machine_id,
            progress, risk_score, cost_estimate, quality_score, test_coverage, revenue_target, goals, metadata
        )
        values (
            'ai-operations-center-2', 'AI Operations Center 2.0', 'platform', 'active',
            'orchestrator', 'brain-gaming-pc', 40, 32, 0, 84, 25, 500000,
            %s::jsonb, %s::jsonb
        )
        on conflict (id) do nothing
        """,
        (
            _json(["distributed AI workforce", "secure laptop orchestration", "zero-budget business creation", "Jayla approval gates"]),
            _json({"owner": "Jayla", "brain_role": "CEO / Brain Orchestrator"}),
        ),
    )


def _insert_business_notes(cur: Any, project_id: str, business: dict[str, Any]) -> int:
    notes = [
        ("mission", "Mission and Offer", f"{business['name']} helps {business['audience']} by offering: {business['offer']}"),
        ("validation_plan", "30-60 Day Validation Plan", "Days 1-3: research. Days 4-7: landing page/sample/outreach. Days 8-14: minimum business setup. Days 15-21: pilots. Days 22-30: automate proven path. Days 31-60: acquisition and profit optimization."),
        ("approval_matrix", "Jayla Approval Matrix", "\n".join(f"- {a}: {b} - {c}" for a, b, c in APPROVAL_MATRIX)),
        ("zero_budget_plan", "Zero Budget Launch Rules", f"Starting budget is $0. Use organic outreach, templates, direct research, free tooling, and manual validation before any paid spend. First sale path: {business['first_sale_path']}"),
        ("kpi_framework", "KPIs", "Track leads, replies, calls, sales, MRR, conversion, CAC, gross margin, refund rate, revision rate, support defects, and time-to-delivery."),
    ]
    created = 0
    for note_type, title, body in notes:
        cur.execute(
            """
            insert into project_notes (project_id, note_type, title, body, source, metadata)
            select %s, %s, %s, %s, 'autonomous-business-os', %s::jsonb
            where not exists (
                select 1 from project_notes where project_id = %s and note_type = %s and title = %s
            )
            returning id
            """,
            (project_id, note_type, title, body, _json({"business_id": business["id"]}), project_id, note_type, title),
        )
        if cur.fetchone():
            created += 1
    return created


def _business_task_description(business: dict[str, Any], phase: str, description: str) -> str:
    return (
        f"Business: {business['name']}\n"
        f"Audience: {business['audience']}\n"
        f"Offer: {business['offer']}\n"
        f"Phase: {phase}\n\n"
        f"Work required: {description}\n\n"
        "Required checks:\n"
        "- Use $0 starting budget assumptions unless Jayla approves spend.\n"
        "- Include evidence, risks, confidence, and next action.\n"
        "- Do not send emails, publish, spend, file legal documents, change accounts, or handle banking.\n"
        "- Use the approval matrix and create a Brain/Jayla approval request for sensitive actions.\n"
        "- Store or report artifacts through the Brain listener/speaker workflow."
    )


def _machine_for_agent(agent_id: str) -> str:
    if agent_id in {"programmer", "website-builder", "qa-prechecker", "deployment-prechecker", "database-optimizer"}:
        return "dev-laptop"
    if agent_id in {"research-lead", "market-intelligence", "grant-scout", "grant-writer", "data-miner", "resale-scout"}:
        return "research-laptop"
    if agent_id in {"business-manager", "finance-manager", "marketing-agent", "lead-generation", "sales-funnel", "customer-success", "social-media"}:
        return "business-laptop"
    return "brain-gaming-pc"


def _json(value: Any) -> str:
    return json.dumps(value, default=str)
