from ai_ops_center.node_mesh import node_mesh_snapshot


def test_node_mesh_maps_business_laptop_to_creative_node():
    mesh = node_mesh_snapshot()
    nodes = mesh["nodes"]

    assert nodes["research-laptop"]["node_id"] == "research-01"
    assert nodes["research-laptop"]["role"] == "research"
    assert nodes["business-laptop"]["node_id"] == "creative-01"
    assert nodes["business-laptop"]["role"] == "creative"
    assert nodes["dev-laptop"]["node_id"] == "development-01"
    assert nodes["dev-laptop"]["role"] == "development"


def test_node_mesh_preserves_brain_authority_and_high_risk_approval():
    mesh = node_mesh_snapshot()

    assert "Brain PC remains scheduler" in mesh["authority"]
    assert "financial_transactions" in mesh["peer_permissions"]["business-laptop"]["cannot_authorize"]
    assert "completed" in mesh["task_states"]
    assert "node.creative.tasks" in mesh["message_channels"]
