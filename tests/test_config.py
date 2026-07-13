from ai_ops_center.config import load_agents, load_machines, load_revenue_strategy, load_yaml


def test_agent_count_is_initial_workforce():
    agents = load_agents()
    assert len(agents) >= 18
    assert len({agent["id"] for agent in agents}) == len(agents)


def test_machine_roles_are_present():
    roles = {machine["role"] for machine in load_machines()}
    assert {"brain", "creative", "research", "development"} <= roles


def test_all_configured_laptops_are_employed_and_live_monitored():
    laptops = {
        machine["id"]: machine
        for machine in load_machines()
        if machine["id"].endswith("-laptop")
    }

    assert set(laptops) == {"business-laptop", "research-laptop", "dev-laptop"}
    assert laptops["business-laptop"]["role"] == "creative"
    assert laptops["research-laptop"]["role"] == "research"
    assert laptops["dev-laptop"]["role"] == "development"
    assert all(machine["workforce_status"] == "employed" for machine in laptops.values())
    assert all(machine["live_status_enabled"] is True for machine in laptops.values())


def test_workforce_and_runtime_statuses_are_independent_dimensions():
    policy = load_yaml("machines.yaml")["status_policy"]

    assert set(policy["workforce_states"]).isdisjoint(policy["runtime_states"])
    assert policy["active_definition"] == {
        "workforce_status": "employed",
        "runtime_state": "online",
    }


def test_live_status_intervals_match_the_worker_and_connectivity_cadence():
    telemetry = load_yaml("machines.yaml")["status_policy"]["telemetry"]

    assert telemetry["heartbeat_expected_seconds"] == 10
    assert telemetry["connectivity_scan_seconds"] == 30
    assert telemetry["worker_stale_after_seconds"] == 60
    assert telemetry["worker_stale_after_seconds"] > telemetry["heartbeat_expected_seconds"]


def test_revenue_target_matches_requested_range():
    target = load_revenue_strategy()["annual_revenue_target"]
    assert target["low"] == 250000
    assert target["high"] == 500000
