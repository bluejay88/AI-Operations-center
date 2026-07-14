"""Independent review gates for the PET Local Conversation batch.

These checks intentionally do not certify or promote catalog features. Strict
xfails are unresolved release evidence, not implementation acceptance.
"""

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")
STYLE = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.css").read_text(encoding="utf-8")
CATALOG = json.loads((ROOT / "config" / "pet_feature_catalog_v1.json").read_text(encoding="utf-8"))
FEATURE_IDS = {"PET-03-01", "PET-03-03", "PET-03-04", "PET-03-08", "PET-03-10"}


def feature_rows():
    rows = CATALOG["features"] if isinstance(CATALOG, dict) else CATALOG
    return {row["feature_id"]: row for row in rows if row.get("feature_id") in FEATURE_IDS}


def test_review_scope_is_exact_and_every_feature_remains_planned():
    rows = feature_rows()
    assert set(rows) == FEATURE_IDS
    assert {row["contract"]["execution_state"] for row in rows.values()} == {"planned"}


def test_chat_output_and_speech_button_attributes_are_html_escaped():
    assert '<p>${escapeHtml(entry.text)}</p>' in SCRIPT
    assert 'data-chat-speak="${escapeHtml(entry.text)}"' in SCRIPT
    assert "escapeHtml(String(entry.name" in SCRIPT


def test_chat_is_advisory_and_cannot_auto_create_work():
    request = SCRIPT[SCRIPT.index('const response = await postJson("/models/query"'):]
    request = request[: request.index("const reply =")]
    assert "auto_create_tasks: false" in request
    assert "Protected, financial, destructive" in request
    assert "require_approval: false" in request  # safe because no task/action is created


def test_microphone_is_user_initiated_and_typed_input_survives_without_it():
    assert '$("#pet-chat-dictate").addEventListener("click", startDictation)' in SCRIPT
    assert "recognition.start()" in SCRIPT
    assert "dictate.disabled = !canListen" in SCRIPT
    assert 'id="pet-chat-input"' in SCRIPT
    assert "Type your message instead" in SCRIPT
    assert "continuous = false" in SCRIPT


def test_speech_playback_is_user_initiated_stoppable_and_not_automatic_on_reply():
    assert '$("#pet-chat-speak").addEventListener("click"' in SCRIPT
    assert 'data-chat-speak="${escapeHtml(entry.text)}"' in SCRIPT
    assert "window.speechSynthesis.cancel()" in SCRIPT
    reply_path = SCRIPT[SCRIPT.index("const reply = String(response.synthesized_response"):]
    reply_path = reply_path[: reply_path.index("} catch (error)")]
    assert "speakText(" not in reply_path


def test_context_is_session_scoped_bounded_clearable_and_visible():
    assert re.search(r'sessionStorage\.getItem\(`aiops\.\$\{config\.machineId\}\.petChat`', SCRIPT)
    assert re.search(r'sessionStorage\.setItem\(`aiops\.\$\{state\.machineId\}\.petChat`', SCRIPT)
    assert not re.search(r'localStorage\.(?:getItem|setItem)\([^\n]*petChat', SCRIPT)
    assert "state.chatHistory.slice(-30)" in SCRIPT
    assert "state.chatHistory.slice(-10)" in SCRIPT
    assert "state.chatHistory = []" in SCRIPT
    assert 'id="pet-chat-context"' in SCRIPT


def test_cancel_boundary_is_honestly_client_side_and_preserves_context():
    assert "new AbortController()" in SCRIPT
    assert "state.chatAbortController.abort()" in SCRIPT
    assert 'error.name === "AbortError"' in SCRIPT
    assert "context kept" in SCRIPT
    assert "/models/cancel" not in SCRIPT


def test_accessibility_and_reduced_motion_contracts_are_present():
    assert 'role="log"' in SCRIPT
    assert 'aria-label="PET conversation transcript"' in SCRIPT
    assert 'role="status" aria-live="polite" aria-atomic="true"' in SCRIPT
    assert 'aria-pressed="false"' in SCRIPT
    assert "@media (prefers-reduced-motion: reduce)" in STYLE
    assert ".pet-chat-actions button { min-height: 40px; }" in STYLE


@pytest.mark.xfail(strict=True, reason="PET-03-08 has explicit stop/cancel but no automatic spoken barge-in detection")
def test_release_gate_detects_automatic_voice_interruption():
    assert "onaudiostart" in SCRIPT and "speechSynthesis.cancel()" in SCRIPT


@pytest.mark.xfail(strict=True, reason="AbortController does not prove the upstream Brain/model computation was cancelled")
def test_release_gate_proves_server_side_model_cancellation():
    assert "/models/cancel" in SCRIPT


@pytest.mark.xfail(strict=True, reason="The UI does not disclose that browser speech recognition may use an external speech service")
def test_release_gate_discloses_speech_processing_boundary():
    assert "speech service" in SCRIPT.lower() or "browser provider" in SCRIPT.lower()


@pytest.mark.xfail(strict=True, reason="No secure-context readiness check is exposed before physical microphone certification")
def test_release_gate_checks_secure_context_for_microphone_use():
    assert "window.isSecureContext" in SCRIPT

