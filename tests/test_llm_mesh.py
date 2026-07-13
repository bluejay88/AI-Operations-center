from ai_ops_center.llm_mesh import classify_prompt, route_prompt


def test_coding_prompt_prefers_local_coder_first():
    route = route_prompt("Fix this Python API traceback and add unit tests", mode="coding")

    assert route["selected"]["profile_id"] == "local_coding"
    assert route["selected"]["provider"] == "ollama"
    assert route["classification"]["mode"] in {"coding", "debugging"}


def test_edge_local_only_blocks_cloud_routes():
    route = route_prompt("Answer this offline edge device question", local_only=True, edge_device=True)

    assert route["selected"]["local_only"] is True
    assert all(candidate["local_only"] for candidate in route["fallback_order"])


def test_sensitive_prompt_moves_local_routes_up():
    route = route_prompt("Summarize this API key and credential rotation plan", mode="qa")

    assert route["classification"]["sensitive"] is True
    assert route["fallback_order"][0]["local_only"] is True


def test_generation_prompt_classification():
    classified = classify_prompt("Generate a landing page and social campaign for a new service")

    assert classified["mode"] == "generation"
    assert classified["complexity"] >= 20
