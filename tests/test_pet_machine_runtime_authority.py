from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ai_ops_center import pet_machine_capabilities as caps
from ai_ops_center.api import dashboard_root
from ai_ops_center.migrations import CHECKSUM_COMPATIBILITY


ROOT = Path(__file__).resolve().parents[1]


def test_migration_018_has_atomic_replay_outbox_and_key_lifecycle():
    sql = (ROOT / "sql" / "migrations" / "018_pet_machine_capability_runtime_authority.sql").read_text(encoding="utf-8").lower()
    assert "consume_pet_machine_execution_nonce" in sql
    assert "on conflict(machine_id, nonce) do nothing" in sql
    assert "pet_machine_capability_outbox" in sql
    assert "idempotency_key" in sql
    assert "publish_pet_machine_capability_dispatch" in sql
    assert "pet_machine_capability_keys" in sql
    assert "revoked_at" in sql and "not_before" in sql and "not_after" in sql
    assert "revoke all" in sql


def test_key_ids_rotate_by_environment_without_changing_code(monkeypatch):
    monkeypatch.setenv("PET_DISPATCH_KEY_ID_DEV_LAPTOP", "dispatch:dev-laptop:v2")
    monkeypatch.setenv("PET_RECEIPT_KEY_ID_DEV_LAPTOP", "receipt:dev-laptop:v7")
    assert caps._configured_key_id("dispatch", "dev-laptop") == "dispatch:dev-laptop:v2"
    assert caps._configured_key_id("receipt", "dev-laptop") == "receipt:dev-laptop:v7"


def test_production_validation_fails_closed_without_registry_and_allowlist(monkeypatch):
    monkeypatch.setenv("PET_KEY_REGISTRY_REQUIRED", "false")
    monkeypatch.delenv("PET_BROWSER_ALLOWED_DOMAINS", raising=False)
    with pytest.raises(RuntimeError, match="not provisioned"):
        caps.validate_machine_capability_settings(production=True)


def test_contract_reports_actual_allowlist_and_disabled_executors(monkeypatch):
    monkeypatch.setenv("PET_BROWSER_ALLOWED_DOMAINS", "chatgpt.com,openai.com,youtube.com")
    for name in ("PET_ENABLE_BROWSER_NAVIGATION", "PET_ENABLE_MUSIC_PLAYBACK", "PET_ENABLE_MUSIC_LIBRARY", "PET_ENABLE_DEVICE_MODEL_CHAT"):
        monkeypatch.setenv(name, "false")
    contract = caps.capability_contracts()
    assert contract["browser"]["allowlist_configured"] is True
    assert contract["runtime_authority"]["executors_enabled"] == []


def test_postgres_replay_guard_calls_atomic_migration_function(monkeypatch):
    calls = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def execute(self, sql, params): calls.append((sql, params))
        def fetchone(self): return {"consume_pet_machine_execution_nonce": True}
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def cursor(self): return Cursor()
        def commit(self): calls.append(("commit", ()))
    monkeypatch.setattr(caps, "connect", lambda **_: Connection())
    accepted = caps.PostgresMachineCapabilityReplayGuard().consume(
        machine_id="dev-laptop", nonce="00000000-0000-0000-0000-000000000001",
        request_id="00000000-0000-0000-0000-000000000002",
        expires_at=datetime.now(UTC) + timedelta(minutes=1), dispatch_sha256="a" * 64,
    )
    assert accepted is True
    assert "consume_pet_machine_execution_nonce" in calls[0][0]


def test_root_redirects_permanently_to_canonical_dashboard():
    response = dashboard_root()
    assert response.status_code == 308
    assert response.headers["location"] == "/dashboard/"


def test_runtime_authority_historical_checksum_compatibility_is_exact():
    assert CHECKSUM_COMPATIBILITY["018"] == {"eea5aac7a3b21fb4e40e1ac199c35f4b13dcbd11c0e2673cc25f5a64cbda95f1"}
