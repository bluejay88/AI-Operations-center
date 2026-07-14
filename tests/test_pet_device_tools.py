from pathlib import Path

import pytest
from fastapi import HTTPException

from ai_ops_center import api
from ai_ops_center.auth import ANONYMOUS


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")
STYLE = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.css").read_text(encoding="utf-8")
CAPABILITIES = (ROOT / "ai_ops_center" / "pet_machine_capabilities.py").read_text(encoding="utf-8")
MINI_DASHBOARDS = [
    (ROOT / "laptop_packages" / machine / "index.html").read_text(encoding="utf-8")
    for machine in ("dev-laptop", "research-laptop", "business-laptop")
]


def test_all_machine_pets_receive_one_shared_governed_tools_surface():
    assert 'section.id = "pet-device-tools"' in SCRIPT
    assert "Governed requests only" in SCRIPT
    assert "only a device receipt can confirm execution" in SCRIPT
    assert ".pet-device-tools" in STYLE


def test_machine_pet_identity_mapping_is_exact():
    assert '"dev-laptop": "development-pet"' in SCRIPT
    assert '"research-laptop": "research-pet"' in SCRIPT
    assert '"business-laptop": "creative-pet"' in SCRIPT
    assert "pet_id: petId" in SCRIPT


def test_url_policy_uses_server_contract_and_fails_closed_client_side():
    assert "state.capabilityContracts?.browser?.allowed_schemes" in SCRIPT
    assert "parsed.username || parsed.password" in SCRIPT
    assert "local and private network targets are not allowed" in SCRIPT
    assert "configured domain allowlist" in SCRIPT
    assert "Denied: URLs cannot contain embedded credentials." in SCRIPT
    assert 'submitMachineCapability("browser_navigation"' in SCRIPT


def test_all_tools_use_one_authoritative_capability_endpoint():
    assert 'postJson("/pet-machine-capabilities/requests"' in SCRIPT
    assert 'getJson("/pet-machine-capabilities/contracts")' in SCRIPT
    assert 'submitMachineCapability("browser_navigation"' in SCRIPT
    assert 'submitMachineCapability("music_playback"' in SCRIPT
    assert 'submitMachineCapability("device_model_chat"' in SCRIPT
    device_section = SCRIPT[SCRIPT.index("async function submitBrowserUrl"):SCRIPT.index("function renderPet")]
    assert 'postJson("/remote-ops"' not in device_section
    assert 'postJson("/collaboration/model-session"' not in device_section


def test_browser_and_music_are_approval_held_by_authoritative_server_contract():
    assert 'capability_type in {"browser_navigation", "music_playback"}' in CAPABILITIES
    assert 'status = "pending_approval" if approval_required else "requested"' in CAPABILITIES
    assert '"DO NOT EXECUTE. Await a separately approved execution message."' in CAPABILITIES


def test_music_requires_safe_local_media_id_and_never_claims_playback():
    assert 'id="device-music-id"' in SCRIPT
    assert 'data-music-action="play"' in SCRIPT
    assert 'data-music-action="pause"' in SCRIPT
    assert 'data-music-action="stop"' in SCRIPT
    assert "Play requires a safe local media ID" in SCRIPT
    assert "no playback state is assumed" in SCRIPT
    assert "Await a machine receipt" in SCRIPT


def test_device_model_chat_is_targeted_to_device_executor_without_success_claim():
    assert 'model_id: "device-default"' in SCRIPT
    assert "machine_id: state.machineId" in SCRIPT
    assert "device-hosted model-chat executor" in CAPABILITIES
    assert '"device_model_chat": model_handler' in CAPABILITIES
    assert '"worker_execution_authorized": False' in CAPABILITIES
    assert "success=${receipt.success_claimed}" in SCRIPT


def test_capability_readiness_and_receipt_truth_are_accessible():
    assert 'return "unverified"' in SCRIPT
    assert "machine receipt" in SCRIPT
    assert '"not reported"' in SCRIPT
    assert "request path online" in SCRIPT
    assert 'role="status" aria-live="polite"' in SCRIPT
    assert 'aria-label="Device capability readiness"' in SCRIPT
    assert "@media (max-width: 560px)" in STYLE


def test_long_worker_state_is_humanized_without_fragmented_desktop_type():
    assert 'machineState.replace(/[_-]+/g, " ")' in SCRIPT
    assert "metricHealth.title = machineState" in SCRIPT
    assert ".metric #metric-health" in STYLE
    assert "word-break: normal" in STYLE


def test_all_machine_dashboards_load_the_latest_shared_pet_ui_assets():
    for dashboard in MINI_DASHBOARDS:
        assert "mini-dashboard.css?v=pet-command-20260713r" in dashboard
        assert "mini-dashboard.js?v=pet-command-20260713r" in dashboard


def test_pet_machine_capability_api_is_unique_and_fails_closed_for_unknown_target():
    paths = [route for route in api.app.routes if route.path == "/pet-machine-capabilities/requests"]
    assert len(paths) == 1
    contract_paths = [route for route in api.app.routes if route.path == "/pet-machine-capabilities/contracts"]
    assert len(contract_paths) == 1
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
        api.pet_machine_capability_request(request, type("Request", (), {"state": type("State", (), {"principal": ANONYMOUS})()})())
    assert error.value.status_code == 422
