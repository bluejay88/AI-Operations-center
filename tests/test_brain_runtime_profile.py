from pathlib import Path

import pytest
from fastapi import HTTPException

from ai_ops_center import api, brain_runtime_profile as runtime


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "migrations" / "013_brain_runtime_identity.sql"


def reservation():
    return {
        "device_id": "brain-gaming-pc",
        "identity_fingerprint": "a" * 64,
        "reserved_by": "migration-013",
        "approval_ref": "migration-013-bootstrap",
        "reserved_at": "2026-07-13T00:00:00Z",
    }


def test_runtime_profile_is_safe_read_only_and_keeps_ledger_planned(monkeypatch):
    monkeypatch.setattr(runtime, "_registered_device", lambda *args, **kwargs: reservation())
    profile = runtime.runtime_profile()
    assert profile["feature_ids"] == [f"BRAIN-01-{item:02d}" for item in range(1, 11)]
    assert profile["ledger_state"] == "P"
    assert profile["durable_identity"]["device_id"] == "brain-gaming-pc"
    assert profile["governance"] == {
        "read_only_api": True,
        "mutation_endpoint_exposed": False,
        "personality_changes_authorized": False,
        "ledger_transition_authorized": False,
    }
    assert "prompt_context" not in profile


def test_readiness_separates_integration_from_operational_certification(monkeypatch):
    monkeypatch.setattr(runtime, "_registered_device", lambda *args, **kwargs: reservation())
    result = runtime.runtime_profile_readiness()
    assert result["integration_ready"] is True
    assert result["operational_certified"] is False
    assert result["ledger_state"] == "P"
    assert "physical_brain_correlation" in result["remaining_gates"]
    assert "governed_ledger_transition" in result["remaining_gates"]


def test_missing_durable_reservation_blocks_integration_readiness(monkeypatch):
    monkeypatch.setattr(runtime, "_registered_device", lambda *args, **kwargs: None)
    result = runtime.runtime_profile_readiness()
    assert result["checks"]["durable_identity_reserved"] is False
    assert result["integration_ready"] is False
    assert result["operational_certified"] is False


def test_laptop_detail_is_config_backed_versioned_and_fail_closed():
    detail = runtime.laptop_runtime_profile("research-laptop")
    assert detail is not None
    assert detail["role"] == "research"
    assert detail["inventory_version"].startswith("machines.yaml:sha256:")
    assert detail["mutation_authorized"] is False
    assert runtime.laptop_runtime_profile("attacker-laptop") is None


def test_registry_rejects_unapproved_mutation_before_database_access():
    registry = runtime.PostgresDeviceIdentityRegistry(
        actor="test-reviewer", approval_ref="approval-1", mutation_authorized=False
    )
    with pytest.raises(PermissionError, match="requires governed approval"):
        registry.reserve("new-device")
    with pytest.raises(PermissionError, match="append-only"):
        registry.release("brain-gaming-pc")


def test_api_exposes_only_get_routes_for_runtime_profile(monkeypatch):
    paths = {
        route.path: route.methods
        for route in api.app.routes
        if route.path.startswith("/brain-runtime-profile")
    }
    assert paths == {
        "/brain-runtime-profile": {"GET"},
        "/brain-runtime-profile/readiness": {"GET"},
        "/brain-runtime-profile/laptops/{machine_id}": {"GET"},
    }
    monkeypatch.setattr(api, "laptop_runtime_profile", lambda machine_id: None)
    with pytest.raises(HTTPException) as error:
        api.brain_laptop_runtime_profile_endpoint("unknown-laptop")
    assert error.value.status_code == 404


def test_migration_013_is_append_only_atomic_and_uniquely_numbered():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "device_id text primary key" in sql
    assert "on conflict (device_id) do nothing" in sql
    assert "before update or delete" in sql
    assert "approval_ref text not null" in sql
    versions = [path.name.split("_", 1)[0] for path in (ROOT / "sql" / "migrations").glob("*.sql")]
    assert len(versions) == len(set(versions))

