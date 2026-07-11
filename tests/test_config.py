from ai_ops_center.config import load_agents, load_machines, load_revenue_strategy


def test_agent_count_is_initial_workforce():
    assert len(load_agents()) == 18


def test_machine_roles_are_present():
    roles = {machine["role"] for machine in load_machines()}
    assert {"brain", "business", "research", "development"} <= roles


def test_revenue_target_matches_requested_range():
    target = load_revenue_strategy()["annual_revenue_target"]
    assert target["low"] == 250000
    assert target["high"] == 500000

