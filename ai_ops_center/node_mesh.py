from __future__ import annotations

from typing import Any


NODE_ROLES: dict[str, dict[str, Any]] = {
    "brain-gaming-pc": {
        "node_id": "brain-01",
        "name": "Brain PC",
        "role": "authority",
        "title": "Mission Control",
        "channels": ["brain.commands", "brain.approvals", "node.all.status", "security.alerts"],
        "capabilities": [
            "executive_decision_engine",
            "scheduler",
            "master_memory",
            "database",
            "security_controller",
            "model_router",
            "audit_controller",
            "quality_gate",
        ],
    },
    "research-laptop": {
        "node_id": "research-01",
        "name": "Laptop 1 Research Node",
        "role": "research",
        "title": "Research Node",
        "channels": ["node.research.tasks", "project.*.events", "node.all.status"],
        "capabilities": [
            "market_research",
            "competitor_analysis",
            "grant_research",
            "trend_analysis",
            "citation_engine",
            "report_creation",
            "opportunity_validation",
        ],
    },
    "business-laptop": {
        "node_id": "creative-01",
        "name": "Laptop 2 Creative Node",
        "role": "creative",
        "title": "Creative Node",
        "channels": ["node.creative.tasks", "project.*.events", "node.all.status"],
        "capabilities": [
            "graphic_design",
            "branding",
            "presentations",
            "social_media",
            "advertising",
            "website_design",
            "creative_writing",
            "customer_deliverable_packaging",
        ],
    },
    "dev-laptop": {
        "node_id": "development-01",
        "name": "Laptop 3 Development Node",
        "role": "development",
        "title": "Development Node",
        "channels": ["node.development.tasks", "project.*.events", "node.all.status"],
        "capabilities": [
            "programming",
            "website_development",
            "automation",
            "python",
            "docker",
            "databases",
            "api",
            "security_testing",
            "deployment",
        ],
    },
}

TASK_STATES = [
    "created",
    "accepted",
    "in_progress",
    "waiting_for_input",
    "delegated",
    "needs_review",
    "needs_correction",
    "blocked",
    "completed",
    "rejected",
    "cancelled",
]

PEER_PERMISSION_RULES = {
    "research-laptop": {
        "can_request": ["research", "validation", "citations", "datasets", "market_stats"],
        "cannot_authorize": ["publishing", "spending", "deployment", "financial_transactions"],
    },
    "business-laptop": {
        "can_request": ["graphics", "layouts", "campaigns", "copy", "asset_revisions"],
        "cannot_authorize": ["code_deployment", "financial_transactions", "credential_changes"],
    },
    "dev-laptop": {
        "can_request": ["builds", "tests", "automation", "technical_review", "scrapers"],
        "cannot_authorize": ["financial_transactions", "public_sending", "bypass_security_policy"],
    },
}


def node_mesh_snapshot() -> dict[str, Any]:
    return {
        "cluster": "brain-mesh-ai-operations-center",
        "transport": "Tailscale private mesh; no public inbound Brain exposure.",
        "authority": "Brain PC remains scheduler, memory, policy, approval, and audit authority.",
        "nodes": NODE_ROLES,
        "task_states": TASK_STATES,
        "continuous_flow_policy": {
            "operating_mode": "24x7",
            "brain_role": "continuously listen, prioritize, route, recover, and audit",
            "worker_role": "claim the next eligible task immediately after completion",
            "transient_states": ["created", "accepted", "in_progress", "delegated", "needs_review", "needs_correction"],
            "hold_states": ["waiting_for_input", "blocked"],
            "hold_requirements": ["machine-readable reason", "responsible owner", "next check or external event"],
            "invariants": [
                "eligible work never waits behind an idle healthy node",
                "expired claims are recovered automatically",
                "operator and peer requests track their executable task evidence",
                "approval and machine-bound waits remain visible and are never bypassed",
            ],
        },
        "message_channels": [
            "brain.commands",
            "brain.approvals",
            "node.research.tasks",
            "node.creative.tasks",
            "node.development.tasks",
            "node.all.status",
            "project.{project_id}.events",
            "security.alerts",
            "quality.reviews",
        ],
        "peer_permissions": PEER_PERMISSION_RULES,
        "handoff_envelope": {
            "task_id": "TASK-1042",
            "from_node": "research-01",
            "to_node": "creative-01",
            "task_type": "create_market_charts",
            "priority": "high",
            "inputs": ["projects/1042/research/market-data.json"],
            "expected_outputs": ["projects/1042/design/market-chart.png"],
            "deadline": "2026-07-14T18:00:00-05:00",
            "permissions": ["read_project_1042", "write_design_folder"],
            "requires_brain_approval": False,
        },
        "security_rules": [
            "Every node action is audited by the Brain.",
            "Nodes may request help directly, but high-risk actions route to Brain/Jayla approval.",
            "Nodes do not automatically trust one another; permissions are role-scoped.",
            "Financial, legal, credential, destructive, public sending, and deployment actions require approval.",
        ],
    }
