from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")
STYLE = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.css").read_text(encoding="utf-8")


def test_explicit_actions_use_two_phase_proposal_and_confirmation_endpoints():
    assert 'postJson("/pet-action-proposals"' in SCRIPT
    assert 'postJson(`/pet-action-proposals/${encodeURIComponent(entry.proposalId)}/confirm`' in SCRIPT
    assert 'confirmed_by: `${state.machineId}/mini-dashboard-chat`' in SCRIPT
    assert 'proposalId: String(response.proposal_id)' in SCRIPT
    assert "This is a proposal only; no capability request or Brain message has been issued." in SCRIPT
    assert "Nothing has been sent yet" in SCRIPT


def test_action_card_exposes_target_action_approval_and_confirm_cancel_controls():
    assert 'class="pet-chat-action-card"' in SCRIPT
    assert "<dt>Target</dt>" in SCRIPT
    assert "<dt>Action</dt>" in SCRIPT
    assert "<dt>Approval</dt>" in SCRIPT
    assert 'data-chat-action-confirm=' in SCRIPT
    assert 'data-chat-action-cancel=' in SCRIPT
    assert ".pet-chat-action-card" in STYLE


def test_normal_questions_still_use_model_chat_and_unhandled_actions_fall_back():
    assert 'await requestPetModelReply(message, personality)' in SCRIPT
    assert 'if (response?.handled === false)' in SCRIPT
    assert 'postJson("/models/query"' in SCRIPT


def test_natural_language_browser_music_and_brain_requests_are_action_candidates():
    assert 'type: "multi_action"' in SCRIPT
    assert 'type: "music_catalog"' in SCRIPT
    assert 'type: "brain_message"' in SCRIPT
    assert "Browser navigation does not prove YouTube playback." in SCRIPT
    assert "no playback is requested" in SCRIPT


def test_receipts_never_claim_device_success_without_backend_truth():
    assert "response?.success_claimed === true" in SCRIPT
    assert "No device execution is claimed until an authoritative machine receipt reports completion." in SCRIPT
    assert "approval_request_id" in SCRIPT
    assert "capability_requests" in SCRIPT


def test_follow_up_yes_or_no_resolves_latest_pending_proposal():
    assert '/^(?:yes|confirm|approve|do it|proceed)$/i.test(message)' in SCRIPT
    assert '/^(?:no|cancel|never mind|nevermind)$/i.test(message)' in SCRIPT
    assert "submitPetConversationAction(pendingAction.actionId)" in SCRIPT
    assert "cancelPetConversationAction(pendingAction.actionId)" in SCRIPT
