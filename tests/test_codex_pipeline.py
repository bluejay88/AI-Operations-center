from ai_ops_center import codex_pipeline


def test_codex_pipeline_routes_to_tasks_speaker_and_team_room(monkeypatch):
    calls = {"operator": [], "speaker": [], "peer": [], "listener": []}

    monkeypatch.setattr(
        codex_pipeline,
        "post_team_chat_message",
        lambda **kwargs: {"id": 44, "subject": kwargs["subject"], "channel": kwargs["channel"]},
    )

    def fake_operator_request(payload, local=False):
        calls["operator"].append(payload)
        return {"request": {"id": len(calls["operator"])}, "task_ids": [100 + len(calls["operator"])]}

    monkeypatch.setattr(codex_pipeline, "create_operator_request", fake_operator_request)
    monkeypatch.setattr(codex_pipeline, "create_speaker_message", lambda **kwargs: calls["speaker"].append(kwargs) or len(calls["speaker"]))
    monkeypatch.setattr(codex_pipeline, "create_peer_request", lambda **kwargs: calls["peer"].append(kwargs) or {"id": len(calls["peer"]), **kwargs})
    monkeypatch.setattr(codex_pipeline, "submit_listener_event", lambda **kwargs: calls["listener"].append(kwargs) or {"event_id": 7, "actions": []})
    monkeypatch.setattr(codex_pipeline, "team_chat_digest", lambda **kwargs: {"messages": [], "summary": {}})

    result = codex_pipeline.pipe_codex_request(
        {
            "title": "Build routed dashboard task",
            "body": "Pipe this from Codex to the Brain and laptops.",
            "target_machines": ["dev-laptop", "research-laptop"],
            "delivery_methods": ["dashboard", "github"],
            "create_peer_requests": True,
        }
    )

    assert result["created_task_ids"] == [101, 102]
    assert len(calls["operator"]) == 2
    assert len(calls["speaker"]) == 2
    assert len(calls["peer"]) == 2
    assert calls["listener"][0]["event_type"] == "codex_pipeline_routed"
