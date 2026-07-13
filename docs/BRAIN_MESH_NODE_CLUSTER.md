# Brain Mesh Node Cluster

The AI Operations Center is a private distributed node cluster. The Brain PC is the authority, scheduler, memory, policy gate, and audit controller. The laptops are expert nodes that can request help, hand off work, critique outputs, and publish status while the Brain keeps the master record.

## Node Map

| Machine ID | Mesh Node | Role | Primary PET |
| --- | --- | --- | --- |
| `brain-gaming-pc` | `brain-01` | Mission Control / authority | Phoenix |
| `research-laptop` | `research-01` | Laptop 1 Research Node | Nova |
| `business-laptop` | `creative-01` | Laptop 2 Creative Node | Prism |
| `dev-laptop` | `development-01` | Laptop 3 Development Node | Byte |

## Responsibilities

Research Node handles market research, competitors, grants, funding, citations, trend analysis, customer research, opportunity validation, reports, and knowledge collection.

Creative Node handles branding, graphic design, presentations, social media, advertising, website design, document layout, creative writing, video/audio concepts, customer deliverable packaging, CRM-adjacent campaign assets, and sales/marketing collateral.

Development Node handles programming, websites, automation, Python, Docker, databases, APIs, testing, security checks, deployment, monitoring, CI/CD, and technical documentation.

Brain handles decisions, scheduling, permissions, memory, databases, quality gates, approvals, security, reports, finance/KPI tracking, conflict resolution, and final delivery approval.

## Communication Rules

Nodes may request specialist help directly through `/collaboration/peer-requests`, but the Brain receives an audit copy through listener and speaker events.

High-risk work requires approval before execution: credentials, money, legal, public sending/posting, destructive changes, customer-sensitive data movement, deployments, and remote control.

Every node publishes heartbeat, queue, progress, errors, metrics, recommendations, and estimated completion. If a node goes stale or battery is critically low, the Brain can reassign work from checkpoints.

## Standard Peer Request

```json
{
  "from_machine_id": "research-laptop",
  "to_machine_id": "business-laptop",
  "request_type": "asset",
  "subject": "Create market comparison graphics",
  "body": "Use the approved competitor dataset and produce chart concepts for the business plan package.",
  "project_id": "project-1042",
  "priority": 88,
  "metadata": {
    "from_node": "research-01",
    "to_node": "creative-01",
    "inputs": ["projects/1042/research/market-data.json"],
    "expected_outputs": ["projects/1042/assets/market-comparison.png"],
    "requires_brain_approval": false
  }
}
```

Use `GET /node-mesh` for the live contract, node IDs, channels, task states, handoff envelope, and permission rules.
