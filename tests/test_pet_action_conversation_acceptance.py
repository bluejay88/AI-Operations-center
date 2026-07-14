"""Acceptance contract for action-capable PET conversations.

These tests deliberately exercise the proposal/confirmation boundary.  A
conversation turn may propose an action, but it must not create work or claim
device success until the user confirms and the governed route returns evidence.
"""

from pathlib import Path

import pytest

from ai_ops_center import pet_conversation_actions as actions


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")
DASHBOARD_SCRIPT = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "ai_ops_center" / "api.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def isolated_proposal_ledger(monkeypatch):
    """Exercise proposal semantics without requiring a live PostgreSQL service."""
    ledger = {}

    def record(**values):
        values.pop("local", None)
        ledger[values["proposal_id"]] = {**values, "status": "proposed", "result": None}

    def claim(proposal_id, local=False):
        row = ledger[proposal_id]
        if row["result"]:
            return dict(row)
        if row["status"] == "confirming":
            return dict(row)
        if row["status"] != "proposed":
            return dict(row)
        row["status"] = "confirming"
        return {**row, "status": "claimed"}

    def complete(proposal_id, result, local=False):
        ledger[proposal_id].update(status="confirmed", result=dict(result))

    def release(proposal_id, local=False):
        ledger[proposal_id]["status"] = "proposed"

    monkeypatch.setattr(actions, "_record_proposal", record)
    monkeypatch.setattr(actions, "_claim_proposal", claim)
    monkeypatch.setattr(actions, "_complete_proposal", complete)
    monkeypatch.setattr(actions, "_release_proposal", release)
    return ledger


def propose(message: str, *, priority: int = 82) -> dict:
    return actions.propose_pet_conversation_action(
        machine_id="dev-laptop",
        pet_id="development-pet",
        message=message,
        requester="dev-laptop/acceptance-test",
        priority=priority,
    )


def test_youtube_is_a_navigation_proposal_and_has_no_side_effect_before_confirmation(monkeypatch):
    calls = []
    monkeypatch.setattr(actions, "submit_capability_request", lambda **kwargs: calls.append(kwargs) or {})

    proposal = propose("open youtube.com")

    assert proposal["handled"] is True
    assert proposal["action_type"] == "browser_navigation"
    assert proposal["status"] == "proposed"
    assert proposal["success_claimed"] is False
    assert proposal["capability_requests"] == []
    assert proposal["brain_message"] is None
    assert calls == []
    assert "navigation" in proposal["summary"].lower()
    assert "play" not in proposal["summary"].lower()


@pytest.mark.parametrize(
    ("message", "action_type"),
    [
        ("play the song Blue in Green", "music_playback"),
        ("list available music", "music_library"),
        ("ask the device model: summarize the active task", "device_model_chat"),
    ],
)
def test_named_music_library_and_device_model_are_explicit_proposals(message, action_type):
    proposal = propose(message)

    assert proposal["handled"] is True
    assert proposal["action_type"] == action_type
    assert proposal["status"] == "proposed"
    assert proposal["success_claimed"] is False
    assert proposal["capability_requests"] == []


def test_music_availability_is_honest_when_the_node_has_no_library_executor(monkeypatch):
    proposal = propose("list available music")
    monkeypatch.setattr(actions, "submit_capability_request", lambda **kwargs: {
        "request_id": "library-request-1",
        "capability_type": kwargs["capability_type"],
        "status": "requested",
        "approval_required": False,
        "approval_request_id": None,
        "success_claimed": False,
    })
    monkeypatch.setattr(actions, "dispatch_approved_request", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("music library executor is not configured")))

    confirmed = actions.confirm_pet_action_proposal(proposal["proposal_id"], confirmed_by="jayla")

    assert confirmed["success_claimed"] is False
    assert confirmed["status"] == "requested"
    request = confirmed["capability_requests"][0]
    assert request["capability_type"] == "music_library"
    assert request["dispatch"]["status"] == "blocked"
    assert "not configured" in request["dispatch"]["detail"]


def test_device_model_confirmation_uses_governed_capability_and_is_idempotent(monkeypatch):
    calls = []

    def fake_submit(**kwargs):
        calls.append(kwargs)
        return {
            "request_id": "model-request-1",
            "capability_type": kwargs["capability_type"],
            "status": "requested",
            "approval_required": False,
            "approval_request_id": None,
            "success_claimed": False,
        }

    monkeypatch.setattr(actions, "submit_capability_request", fake_submit)
    monkeypatch.setattr(actions, "dispatch_approved_request", lambda request_id, actor, local=False: {
        "request_id": request_id, "status": "dispatched", "success_claimed": False,
    })
    proposal = propose("ask the device model: explain this node's queue")

    first = actions.confirm_pet_action_proposal(proposal["proposal_id"], confirmed_by="jayla")
    second = actions.confirm_pet_action_proposal(proposal["proposal_id"], confirmed_by="jayla")

    assert len(calls) == 1
    assert calls[0]["capability_type"] == "device_model_chat"
    assert calls[0]["machine_id"] == "dev-laptop"
    assert first == second
    assert first["status"] == "dispatched"
    assert first["success_claimed"] is False


def test_confirmed_high_priority_brain_enhancement_is_durable_and_idempotent(monkeypatch):
    calls = []

    def fake_create(payload, local=False):
        calls.append((payload, local))
        return {"request": {"id": 41, "priority": payload["priority"]}, "task_ids": [901]}

    monkeypatch.setattr(actions, "create_operator_request", fake_create)
    monkeypatch.setattr(actions, "post_team_chat_message", lambda **_kwargs: {"id": 77})
    proposal = propose(
        "send high-priority enhancement request to the Brain: add PET action receipts to the dashboard"
    )

    assert proposal["status"] == "proposed"
    assert calls == []
    first = actions.confirm_pet_action_proposal(proposal["proposal_id"], confirmed_by="jayla")
    second = actions.confirm_pet_action_proposal(proposal["proposal_id"], confirmed_by="jayla")

    assert len(calls) == 1
    payload = calls[0][0]
    assert payload["target_machine_id"] == "brain-gaming-pc"
    assert payload["target_agent_id"] == "project-coordinator"
    assert payload["priority"] >= 90
    assert payload["metadata"]["source"] == "pet_conversation"
    assert first == second
    assert first["brain_message"]["operator_request_id"] == 41
    assert first["brain_message"]["task_ids"] == [901]
    assert first["success_claimed"] is False


def test_confirmation_routes_are_explicit_and_the_transcript_requires_a_user_click():
    assert '@app.post("/pet-action-proposals")' in API
    assert '@app.post("/pet-action-proposals/{proposal_id}/confirm")' in API
    assert 'postJson("/pet-action-proposals"' in SCRIPT
    assert "data-chat-action-confirm" in SCRIPT
    assert "Confirm request" in SCRIPT
    assert "/confirm`" in SCRIPT
    assert "proposal only; no capability request or Brain message has been issued" in SCRIPT
    assert "Nothing has been sent yet" in SCRIPT
    assert "No device execution is claimed until an authoritative machine receipt" in SCRIPT


def test_main_pet_card_popout_requires_current_readiness_worker_and_fresh_ssh():
    assert "function petNodeIsFullyOnline" in DASHBOARD_SCRIPT
    assert 'String(readiness.state || "unknown").toLowerCase() === "online"' in DASHBOARD_SCRIPT
    assert '["ssh-22", "ssh-22-brain-to-laptop"].includes(connection.channel)' in DASHBOARD_SCRIPT
    assert 'String(connection.status || "").toLowerCase() === "online"' in DASHBOARD_SCRIPT
    assert "connection.is_stale !== true" in DASHBOARD_SCRIPT
    assert "readinessFresh" in DASHBOARD_SCRIPT
    assert "data-pet-dashboard-popout" in DASHBOARD_SCRIPT
    assert "/laptop-packages/" in DASHBOARD_SCRIPT
    assert "window.open" in DASHBOARD_SCRIPT
    assert "dashboard-popout" not in SCRIPT
