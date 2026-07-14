import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")
STYLE = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.css").read_text(encoding="utf-8")
CATALOG = json.loads((ROOT / "config" / "pet_feature_catalog_v1.json").read_text(encoding="utf-8"))
FEATURE_IDS = {"PET-03-01", "PET-03-03", "PET-03-04", "PET-03-08", "PET-03-10"}


def catalog_features():
    rows = CATALOG["features"] if isinstance(CATALOG, dict) else CATALOG
    return {row["feature_id"]: row for row in rows if row.get("feature_id") in FEATURE_IDS}


def test_exact_conversation_batch_is_present_and_remains_planned():
    features = catalog_features()
    assert set(features) == FEATURE_IDS
    assert all(row["contract"]["execution_state"] == "planned" for row in features.values())
    assert 'data-feature-ids", "PET-03-01 PET-03-03 PET-03-04 PET-03-08 PET-03-10"' in SCRIPT


def test_text_chat_uses_audited_model_route_without_task_creation():
    assert 'postJson("/models/query"' in SCRIPT
    assert "auto_create_tasks: false" in SCRIPT
    assert "require_approval: false" in SCRIPT
    assert 'id="pet-chat-form"' in SCRIPT
    assert "state.chatHistory.push({ role: \"user\"" in SCRIPT


def test_dictation_is_user_initiated_and_fails_to_typed_input():
    assert "window.SpeechRecognition || window.webkitSpeechRecognition" in SCRIPT
    assert 'id="pet-chat-dictate"' in SCRIPT
    assert 'addEventListener("click", startDictation)' in SCRIPT
    assert "Dictation is unavailable. Type your message instead." in SCRIPT
    assert "recognition.interimResults = true" in SCRIPT
    assert "window.isSecureContext" in SCRIPT
    assert 'navigator.permissions.query({ name: "microphone" })' in SCRIPT
    assert "browser or operating-system speech provider may process audio" in SCRIPT


def test_playback_and_interruption_have_explicit_controls():
    assert "SpeechSynthesisUtterance" in SCRIPT
    assert 'id="pet-chat-stop"' in SCRIPT
    assert 'id="pet-chat-cancel"' in SCRIPT
    assert "state.chatAbortController.abort()" in SCRIPT
    assert 'event.key === "Escape"' in SCRIPT
    assert "window.speechSynthesis.cancel()" in SCRIPT
    assert "no automatic barge-in" in SCRIPT
    assert "/models/query/${encodeURIComponent(requestId)}/cancel" in SCRIPT
    assert "upstream completion is unknown" in SCRIPT


def test_context_is_bounded_session_only_and_clearable():
    assert "sessionStorage.setItem" in SCRIPT
    assert "state.chatHistory.slice(-30)" in SCRIPT
    assert "state.chatHistory.slice(-11, -1)" in SCRIPT
    assert "conversation_history: conversationHistory" in SCRIPT
    assert "content: String(entry.text || \"\").slice(0, 800)" in SCRIPT
    assert "state.chatHistory = []" in SCRIPT


def test_voice_ui_has_accessible_state_and_reduced_motion_fallback():
    assert 'role="status" aria-live="polite" aria-atomic="true"' in SCRIPT
    assert 'aria-pressed="false"' in SCRIPT
    assert "@media (prefers-reduced-motion: reduce)" in STYLE
    assert ".sr-only" in STYLE
