from __future__ import annotations

import json
from typing import Any


PROJECT_ID = "ai-operations-center-2"

FEATURE_DOMAINS: list[dict[str, Any]] = [
    {"id": "brain-identity", "name": "Core Brain Identity", "agent_id": "orchestrator", "machine_id": "brain-gaming-pc"},
    {"id": "pet-fleet", "name": "PET Fleet Management", "agent_id": "project-coordinator", "machine_id": "brain-gaming-pc"},
    {"id": "command-control", "name": "Command and Control", "agent_id": "orchestrator", "machine_id": "brain-gaming-pc"},
    {"id": "multi-agent", "name": "Multi-Agent Intelligence", "agent_id": "rubric-auditor", "machine_id": "brain-gaming-pc"},
    {"id": "model-routing", "name": "AI Model Routing", "agent_id": "orchestrator", "machine_id": "brain-gaming-pc"},
    {"id": "memory", "name": "Memory and Knowledge", "agent_id": "database-optimizer", "machine_id": "dev-laptop"},
    {"id": "research", "name": "Research and Intelligence", "agent_id": "research-lead", "machine_id": "research-laptop"},
    {"id": "strategy", "name": "Business and Creative Strategy", "agent_id": "business-manager", "machine_id": "business-laptop"},
    {"id": "finance", "name": "Financial Intelligence", "agent_id": "finance-manager", "machine_id": "brain-gaming-pc"},
    {"id": "decision-engine", "name": "Autonomous Decision Engine", "agent_id": "orchestrator", "machine_id": "brain-gaming-pc"},
    {"id": "security", "name": "Security Command Center", "agent_id": "security-monitor", "machine_id": "brain-gaming-pc"},
    {"id": "governance", "name": "Governance and Permissions", "agent_id": "rubric-auditor", "machine_id": "brain-gaming-pc"},
    {"id": "customer-ops", "name": "Customer and Creative Operations", "agent_id": "business-manager", "machine_id": "business-laptop"},
    {"id": "fulfillment", "name": "Creative Fulfillment and Deliverables", "agent_id": "content-engine", "machine_id": "business-laptop"},
    {"id": "marketing", "name": "Creative Marketing Command Center", "agent_id": "social-media", "machine_id": "business-laptop"},
    {"id": "infrastructure", "name": "Website and Infrastructure Control", "agent_id": "website-builder", "machine_id": "dev-laptop"},
    {"id": "development", "name": "Coding and Development", "agent_id": "programmer", "machine_id": "dev-laptop"},
    {"id": "communication", "name": "Communication and Collaboration", "agent_id": "project-coordinator", "machine_id": "brain-gaming-pc"},
    {"id": "advanced", "name": "Advanced Command Abilities", "agent_id": "orchestrator", "machine_id": "brain-gaming-pc"},
    {"id": "resilience", "name": "Resilience, Recovery, and Self-Improvement", "agent_id": "security-monitor", "machine_id": "brain-gaming-pc"},
]

FEATURE_ACTIONS = [
    "Define policy",
    "Design workflow",
    "Build data model",
    "Create API contract",
    "Wire dashboard",
    "Add worker support",
    "Add audit evidence",
    "Create test fixture",
    "Run simulation",
    "Document runbook",
    "Add approval gate",
    "Add rollback plan",
    "Benchmark performance",
    "Score quality",
    "Route to model mesh",
    "Add import/export",
    "Add notification",
    "Add report view",
    "Add failure recovery",
    "Verify security",
    "Measure business value",
    "Create operator control",
    "Add peer collaboration",
    "Tune thresholds",
    "Prepare human test",
]


def enterprise_feature_catalog() -> dict[str, Any]:
    return {
        "project_id": PROJECT_ID,
        "total_features": 500,
        "domain_count": len(FEATURE_DOMAINS),
        "features_per_domain": 25,
        "domains": [
            {
                **domain,
                "features": [
                    {
                        "feature_number": index + 1,
                        "global_number": domain_index * 25 + index + 1,
                        "title": f"{FEATURE_ACTIONS[index]} for {domain['name']}",
                        "approval_policy": _approval_policy(domain["id"], index),
                    }
                    for index in range(25)
                ],
            }
            for domain_index, domain in enumerate(FEATURE_DOMAINS)
        ],
        "governance": {
            "low_risk": "May be implemented by workers with audit logs.",
            "medium_risk": "Requires Brain review and rollback evidence before execution.",
            "high_risk": "Requires explicit Jayla approval before credentials, money, legal, customer, public, destructive, or remote-control changes.",
        },
    }


def seed_enterprise_feature_backlog(local: bool = False) -> dict[str, Any]:
    from .db import connect

    catalog = enterprise_feature_catalog()
    created = 0
    existing = 0
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            for domain in catalog["domains"]:
                for feature in domain["features"]:
                    number = feature["global_number"]
                    dedupe_key = f"enterprise-feature-500:{number:03d}:{domain['id']}"
                    priority = 99 if number <= 60 else 91 if number <= 180 else 82 if number <= 340 else 70
                    description = (
                        f"Enterprise feature #{number}/500 from {domain['name']}. "
                        f"Action: {feature['title']}. "
                        f"Approval policy: {feature['approval_policy']}. "
                        "Produce design notes, implementation steps, test evidence, security notes, rollback plan, and human-testing instructions."
                    )
                    cur.execute(
                        """
                        insert into tasks (title, agent_id, category, description, priority, metadata)
                        select %s, %s, 'enterprise_feature', %s, %s, %s::jsonb
                        where not exists (
                            select 1 from tasks where metadata->>'dedupe_key' = %s
                        )
                        returning id
                        """,
                        (
                            f"Enterprise feature {number:03d}: {feature['title']}",
                            domain["agent_id"],
                            description,
                            priority,
                            json.dumps(
                                {
                                    "project_id": PROJECT_ID,
                                    "dedupe_key": dedupe_key,
                                    "feature_number": number,
                                    "domain_id": domain["id"],
                                    "domain": domain["name"],
                                    "machine_id": domain["machine_id"],
                                    "approval_policy": feature["approval_policy"],
                                    "feature_catalog": "brain-pc-500",
                                }
                            ),
                            dedupe_key,
                        ),
                    )
                    if cur.fetchone():
                        created += 1
                    else:
                        existing += 1
            cur.execute(
                """
                insert into audit_logs (actor, action, entity_type, entity_id, summary, metadata)
                values ('brain-gaming-pc', 'seed_enterprise_feature_backlog', 'project', %s, %s, %s::jsonb)
                """,
                (
                    PROJECT_ID,
                    f"Seeded Brain PC 500 enterprise feature backlog: {created} created, {existing} existing.",
                    json.dumps({"created": created, "existing": existing, "total": 500}),
                ),
            )
        conn.commit()
    return {"created": created, "existing": existing, "total": 500, "domains": len(FEATURE_DOMAINS)}


def _approval_policy(domain_id: str, index: int) -> str:
    high_risk_domains = {"security", "governance", "finance", "customer-ops", "infrastructure"}
    if domain_id in high_risk_domains or index in {10, 11, 19}:
        return "high_risk_requires_jayla_approval"
    if index in {3, 4, 5, 8, 12, 15, 18, 23}:
        return "medium_risk_requires_brain_review"
    return "low_risk_worker_allowed_with_audit"
