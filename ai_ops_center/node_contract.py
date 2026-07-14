from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .llm_mesh import mesh_status


ROOT = Path(__file__).resolve().parent.parent
AGENTS_CONFIG = ROOT / "config" / "agents.yaml"
MACHINES_CONFIG = ROOT / "config" / "machines.yaml"

APPROVAL_GATES = [
    "spending_money",
    "banking_or_finance_changes",
    "legal_or_tax_filings",
    "sending_email_or_customer_messages",
    "public_deployment_or_publishing",
    "credential_or_account_changes",
    "destructive_filesystem_or_database_changes",
    "remote_control_outside_approved_policy",
]

CORE_ENDPOINTS = {
    "health": "GET /health",
    "readiness": "GET /readiness.json",
    "tasks": "GET /tasks",
    "task_detail": "GET /tasks/{task_id}",
    "task_create": "POST /tasks",
    "codex_pipeline": "POST /codex/pipeline",
    "codex_pipeline_snapshot": "GET /codex/pipeline",
    "project_intake_workspaces": "GET /project-intake/workspaces",
    "project_intake_import": "POST /project-intake/import-scan",
    "project_intake_route": "POST /project-intake/route",
    "listener_publish": "POST /listener/events",
    "speaker_feed": "GET /speaker/feed/{machine_id}",
    "speaker_ack": "POST /speaker/messages/{message_id}/ack",
    "team_chat": "GET /team-chat",
    "team_chat_post": "POST /team-chat/post",
    "team_chat_digest": "GET /team-chat/digest",
    "brain_decision": "POST /team-chat/brain-decision",
    "peer_request": "POST /collaboration/peer-requests",
    "peer_response": "POST /collaboration/peer-requests/{request_id}/respond",
    "handoff": "POST /collaboration/handoff",
    "model_session": "POST /collaboration/model-session",
    "llm_mesh_status": "GET /llm-mesh/status",
    "llm_mesh_route": "POST /llm-mesh/route",
    "llm_mesh_query": "POST /llm-mesh/query",
    "device_telemetry": "POST /ops2/device-telemetry",
    "connections": "POST /connections",
    "approvals": "GET /approvals",
    "approval_request": "POST /approvals",
}


def node_contract(machine_id: str, brain_host: str = "100.70.49.32") -> dict[str, Any]:
    machines = _load_yaml(MACHINES_CONFIG).get("machines", [])
    agents = _load_yaml(AGENTS_CONFIG).get("agents", [])
    machine = next((item for item in machines if item.get("id") == machine_id), None)
    if not machine:
        raise ValueError(f"Unknown machine_id {machine_id!r}")

    assigned_agents = [agent for agent in agents if agent.get("machine") == machine_id]
    brain_agents = [agent for agent in agents if agent.get("machine") == "brain-gaming-pc"]
    peer_machines = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "role": item.get("role"),
            "responsibilities": item.get("responsibilities", []),
        }
        for item in machines
        if item.get("id") != machine_id
    ]
    base_url = f"http://{brain_host}:8088"
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "machine": {
            "id": machine_id,
            "name": machine.get("name"),
            "role": machine.get("role"),
            "capacity_weight": machine.get("capacity_weight"),
            "responsibilities": machine.get("responsibilities", []),
            "heartbeat_expected_seconds": _load_yaml(MACHINES_CONFIG).get("status_policy", {})
            .get("telemetry", {})
            .get("heartbeat_expected_seconds", 10),
        },
        "brain": {
            "id": "brain-gaming-pc",
            "api_base_url": base_url,
            "llm_router_url": f"http://{brain_host}:8091",
            "source_of_truth": ["Brain API", "PostgreSQL", "GitHub repository", "speaker/listener bus"],
        },
        "assigned_agents": [_agent_summary(agent) for agent in assigned_agents],
        "brain_support_agents": [_agent_summary(agent) for agent in brain_agents],
        "peer_machines": peer_machines,
        "endpoints": {name: f"{method_path.split(' ', 1)[0]} {base_url}{method_path.split(' ', 1)[1]}" for name, method_path in CORE_ENDPOINTS.items()},
        "llm_mesh": mesh_status(),
        "operating_loop": [
            "Pull latest GitHub bundle before starting work.",
            "Publish heartbeat and device telemetry at least every 10 seconds while active.",
            "Read speaker feed, acknowledge messages, and publish receipt events.",
            "Claim only eligible tasks assigned to this machine or routed by the Brain steward.",
            "Use /llm-mesh/route before model work; use /llm-mesh/query for approved model execution.",
            "Publish progress, logs, errors, blockers, recommendations, ETA, and completion evidence to /listener/events.",
            "Post team-room updates for major decisions, questions, model results, handoffs, blockers, and completion summaries.",
            "Read /team-chat/digest before making important recommendations so the node understands current Brain/laptop/model context.",
            "Accept Codex-piped work through /codex/pipeline and speaker messages, then report task/project feedback back through team-chat, listener events, or peer responses.",
            "Run docker/scan-projects-to-brain.ps1 to publish local Codex/workspace project scans through /project-intake/import-scan.",
            "When a laptop creates new work for another laptop, use /codex/pipeline for Brain-visible task routing or /collaboration/peer-requests for specialist help.",
            "Use /collaboration/peer-requests for research, QA, assets, stats, security review, diagnostics, and handoff help.",
            "Respond to peer requests with status, artifacts, quality_score, assumptions, risks, and next action.",
            "Never duplicate active work; check current task, peer request, and approval status first.",
            "Commit/push checkpoint notes when battery is critically low or before handing off work.",
        ],
        "message_schema": {
            "listener_event": {
                "source_type": "machine",
                "source_id": machine_id,
                "event_type": "workload_update|task_completed|error|recommendation|peer_request_response|model_result",
                "subject": "short title",
                "body": "evidence-rich update",
                "priority": "1-100",
                "metadata": {"machine_id": machine_id, "agent_id": "assigned agent id", "task_id": "optional"},
            },
            "peer_request": {
                "from_machine_id": machine_id,
                "to_machine_id": "peer machine id",
                "request_type": "research|asset|content|stats|code_review|qa|security_review|business_input|diagnostic|handoff_help",
                "subject": "specific ask",
                "body": "context, expected output, deadline, rubric",
                "priority": "1-100",
            },
            "team_chat_message": {
                "channel": "operations|executive|development|research|business|security|models",
                "thread_key": "global, task id, project id, or named initiative",
                "actor_type": "machine|agent|model|brain|workflow|human",
                "actor_id": "machine, agent, model, or workflow id",
                "message_type": "update|decision|direction|question|answer|feedback|handoff|blocker|model_result|security|audit",
                "subject": "short title",
                "body": "full context, evidence, reasoning, and next action",
                "decision": "optional CEO/Brain decision",
                "direction": "optional instruction/question for laptops or agents",
            },
            "codex_pipeline": {
                "title": "Codex-originated work title",
                "body": "full request, acceptance criteria, context, and constraints",
                "target_machines": ["brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop"],
                "delivery_methods": ["dashboard", "github", "pdf", "docx", "email"],
                "create_peer_requests": "true when laptops should coordinate with each other",
                "metadata": {"source": "codex", "rubric": "evidence, tests, blockers, next action"},
            },
            "project_intake_scan": {
                "source": "codex-project-scanner",
                "machine_id": machine_id,
                "projects": [{"name": "project", "path": "local path", "kind": "python|javascript|web|folder", "flag_counts": {}}],
            },
            "completion_evidence": ["objective", "actions_taken", "files_or_artifacts", "tests_or_sources", "risks", "next_action"],
        },
        "approval_gates": APPROVAL_GATES,
        "security_rules": [
            "Use Tailscale routes for Brain communication whenever possible.",
            "Do not send private keys, API keys, passwords, tokens, banking details, or customer secrets in listener events.",
            "Remote-control actions must flow through approvals/remote-ops unless already pre-approved by policy.",
            "Prefer local/Ollama routing for credential, finance, private, or sensitive prompts.",
            "All meaningful work must be auditable through task status, listener events, peer requests, or Git commits.",
        ],
    }


def _agent_summary(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": agent.get("id"),
        "name": agent.get("name"),
        "category": agent.get("category"),
        "mission": agent.get("mission"),
        "cadence": agent.get("cadence"),
        "tools": agent.get("tools", []),
        "guardrails": agent.get("guardrails", []),
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
