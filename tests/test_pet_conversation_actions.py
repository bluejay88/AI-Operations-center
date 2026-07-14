from ai_ops_center import pet_conversation_actions as actions


def test_transcript_browser_and_named_song_become_two_honest_requests() -> None:
    action_type, payload, summary = actions._plan_action(
        "I want to test this. Open up a web browser and go to youtube.com and then play Slow Down."
    )
    assert action_type == "multi_action"
    assert payload["actions"] == [
        {"action_type": "browser_navigation", "payload": {"url": "https://youtube.com"}},
        {"action_type": "music_playback", "payload": {"command": "play", "media_query": "Slow Down"}},
    ]
    assert "does not claim YouTube playback" in summary


def test_transcript_music_catalog_device_model_and_brain_variants_are_recognized() -> None:
    assert actions._plan_action("Can you tell me what music is available on this device?")[0] == "music_library"
    assert actions._plan_action("Can I chat with the ChatGPT model hosted on this device?")[0] == "device_model_chat"
    planned = actions._plan_action("I want you to send over a high-priority enhancement request to the Brain: add more PET tools")
    assert planned[0] == "brain_communication"
    assert planned[1]["priority"] == 90


def test_proposal_is_side_effect_free_and_returns_confirmation_contract(monkeypatch) -> None:
    monkeypatch.setenv("PET_BROWSER_ALLOWED_DOMAINS", "youtube.com")
    recorded = []
    monkeypatch.setattr(actions, "_record_proposal", lambda **kwargs: recorded.append(kwargs))
    monkeypatch.setattr(actions, "submit_capability_request", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must wait for confirmation")))
    result = actions.propose_pet_conversation_action(
        machine_id="dev-laptop", pet_id="development-pet", message="open youtube.com",
    )
    assert result["handled"] is True
    assert result["status"] == "proposed"
    assert result["proposal_id"]
    assert result["capability_requests"] == []
    assert result["success_claimed"] is False
    assert recorded[0]["payload"] == {"url": "https://youtube.com"}


def test_confirmation_submits_capability_and_never_claims_machine_success(monkeypatch) -> None:
    proposal_id = "00000000-0000-0000-0000-000000000001"
    monkeypatch.setattr(actions, "_claim_proposal", lambda *args, **kwargs: {
        "proposal_id": proposal_id, "status": "claimed", "result": None,
        "machine_id": "dev-laptop", "pet_id": "development-pet", "requester": "mini-dashboard",
        "priority": 60, "action_type": "browser_navigation", "payload": {"url": "https://youtube.com"},
        "summary": "Navigate after confirmation.",
    })
    monkeypatch.setattr(actions, "submit_capability_request", lambda **kwargs: {
        "request_id": "request-1", "status": "pending_approval", "approval_required": True,
        "approval_request_id": 41, "machine_receipt_id": None, "success_claimed": False,
    })
    completed = []
    monkeypatch.setattr(actions, "_complete_proposal", lambda *args, **kwargs: completed.append(args[1]))
    result = actions.confirm_pet_action_proposal(proposal_id, "jayla")
    assert result["status"] == "pending_approval"
    assert result["capability_requests"][0]["approval_request_id"] == 41
    assert result["success_claimed"] is False
    assert completed == [result]


def test_brain_confirmation_creates_durable_operator_request(monkeypatch) -> None:
    proposal_id = "00000000-0000-0000-0000-000000000002"
    monkeypatch.setattr(actions, "_claim_proposal", lambda *args, **kwargs: {
        "proposal_id": proposal_id, "status": "claimed", "result": None,
        "machine_id": "dev-laptop", "pet_id": "development-pet", "requester": "mini-dashboard",
        "priority": 90, "action_type": "brain_communication",
        "payload": {"body": "Add more PET tools", "priority": 90}, "summary": "Brain request prepared.",
    })
    operator_calls = []
    monkeypatch.setattr(actions, "create_operator_request", lambda payload, local=False: operator_calls.append(payload) or {"request": {"id": 77}, "task_ids": [88]})
    monkeypatch.setattr(actions, "post_team_chat_message", lambda **kwargs: {"id": 99})
    monkeypatch.setattr(actions, "_complete_proposal", lambda *args, **kwargs: None)
    result = actions.confirm_pet_action_proposal(proposal_id, "jayla")
    assert operator_calls[0]["priority"] == 90
    assert result["brain_message"]["operator_request_id"] == 77
    assert result["brain_message"]["task_ids"] == [88]
    assert result["success_claimed"] is False
