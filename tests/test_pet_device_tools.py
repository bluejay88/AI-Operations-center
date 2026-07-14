from pathlib import Path

import pytest
from fastapi import HTTPException

from ai_ops_center import api
from ai_ops_center import remote_ops


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")
STYLE = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.css").read_text(encoding="utf-8")
COLLABORATION = (ROOT / "ai_ops_center" / "collaboration.py").read_text(encoding="utf-8")


def test_all_machine_pets_receive_one_shared_governed_tools_surface():
    assert 'section.id = "pet-device-tools"' in SCRIPT
    assert "state.machineId" in SCRIPT
    assert "Governed requests only" in SCRIPT
    assert "only a device receipt can confirm execution" in SCRIPT
    assert ".pet-device-tools" in STYLE


def test_url_policy_allows_only_http_s_without_credentials():
    assert 'new Set(["http:", "https:"])' in SCRIPT
    assert "parsed.username || parsed.password" in SCRIPT
    assert "Denied: only HTTP(S) URLs are allowed." in SCRIPT
    assert "Denied: URLs cannot contain embedded credentials." in SCRIPT
    assert 'operation_type: operationType' in SCRIPT
    assert '"open_local_browser_url"' in SCRIPT


def test_browser_and_music_operations_are_request_scoped_and_approval_gated(monkeypatch):
    monkeypatch.setattr(remote_ops, "_machine_role", lambda *_args, **_kwargs: "business")
    for operation in ["open_local_browser_url", "local_music_play", "local_music_pause", "local_music_stop"]:
        decision = remote_ops.evaluate_remote_operation("business-laptop", operation, f"Explicit user request for {operation}")
        assert decision["allowed_for_role"] is True
        assert decision["blocked"] is False
        assert decision["requires_approval"] is True
        assert decision["risk_level"] == "high"


def test_music_ui_never_claims_local_playback_from_api_acceptance():
    assert 'data-music-action="play"' in SCRIPT
    assert 'data-music-action="pause"' in SCRIPT
    assert 'data-music-action="stop"' in SCRIPT
    assert "no playback state is assumed" in SCRIPT
    assert "Await a node completion receipt" in SCRIPT


def test_device_model_chat_is_targeted_and_ollama_only():
    assert 'postJson("/collaboration/model-session"' in SCRIPT
    assert "machine_id: state.machineId" in SCRIPT
    assert 'providers: ["ollama"]' in SCRIPT
    assert "Cloud fallback is not requested" in SCRIPT
    assert 'providers == ["ollama"]' in COLLABORATION
    assert "Do not fall back to a cloud provider" in COLLABORATION
    assert '"local_only": local_only' in COLLABORATION


def test_capability_readiness_distinguishes_reported_completion_from_unknown():
    assert 'return "unverified"' in SCRIPT
    assert "reported complete" in SCRIPT
    assert '"not reported"' in SCRIPT
    assert "request path online" in SCRIPT
    assert "Queued for ${state.machineId}" in SCRIPT


def test_device_tools_have_responsive_and_accessible_receipts():
    assert 'role="status" aria-live="polite"' in SCRIPT
    assert 'aria-label="Device capability readiness"' in SCRIPT
    assert "@media (max-width: 560px)" in STYLE
    assert ".device-action-receipt" in STYLE


def test_pet_machine_capability_api_exposes_contract_and_fails_closed_for_unknown_target():
    contract = api.pet_machine_capability_contracts()
    assert "browser_navigation" in contract["capability_types"]
    request = api.PetMachineCapabilityRequest(
        machine_id="attacker-laptop",
        pet_id="creative-pet",
        capability_type="browser_navigation",
        payload={"url": "https://example.com"},
        requester="test",
    )
    with pytest.raises(HTTPException) as error:
        api.pet_machine_capability_request(request)
    assert error.value.status_code == 422
