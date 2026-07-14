from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ai_ops_center.pet_instruction_protocol import InMemoryReplayGuard, PostgresReplayGuard, sign_instruction, verify_instruction


NOW = datetime(2026, 7, 13, 18, 0, tzinfo=timezone.utc)
SECRET = b"brain-instruction-test-secret-32-bytes-minimum"


def _unsigned(**overrides):
    value = {
        "instruction_id": "instruction-0001",
        "nonce": "nonce-00000001",
        "signer_id": "brain-gaming-pc",
        "target_machine_id": "dev-laptop",
        "issued_at": (NOW - timedelta(seconds=5)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        "payload": {"action": "connectivity_probe", "priority": 90},
    }
    value.update(overrides)
    return value


def _verify(envelope, guard=None):
    return verify_instruction(
        envelope,
        expected_machine_id="dev-laptop",
        secret_for_signer=lambda signer: SECRET if signer == "brain-gaming-pc" else None,
        replay_guard=guard or InMemoryReplayGuard(),
        now=NOW,
    )


def test_valid_signed_instruction_is_accepted_once():
    decision = _verify(sign_instruction(_unsigned(), SECRET))
    assert decision.accepted is True
    assert decision.code == "accepted"
    assert decision.feature_id == "PET-02-05"


def test_malformed_instruction_fails_closed():
    decision = _verify({"instruction_id": "short"})
    assert decision.accepted is False
    assert decision.code == "malformed_instruction"
    assert decision.feature_id == "PET-02-04"


def test_payload_tampering_invalidates_signature():
    envelope = sign_instruction(_unsigned(), SECRET)
    envelope["payload"]["priority"] = 1
    decision = _verify(envelope)
    assert decision.code == "invalid_signature"
    assert decision.feature_id == "PET-02-05"


def test_expired_and_excessive_ttl_instructions_are_rejected():
    expired = sign_instruction(_unsigned(expires_at=(NOW - timedelta(seconds=1)).isoformat()), SECRET)
    long_lived = sign_instruction(_unsigned(expires_at=(NOW + timedelta(days=2)).isoformat()), SECRET)
    assert _verify(expired).code == "expired_or_invalid_time"
    assert _verify(long_lived).code == "ttl_exceeds_policy"


def test_wrong_target_is_rejected_after_signature_verification():
    envelope = sign_instruction(_unsigned(target_machine_id="business-laptop"), SECRET)
    decision = _verify(envelope)
    assert decision.code == "wrong_target"
    assert decision.feature_id == "PET-02-07"


def test_nonce_is_consumed_atomically_and_replay_is_rejected():
    guard = InMemoryReplayGuard()
    envelope = sign_instruction(_unsigned(), SECRET)
    assert _verify(envelope, guard).accepted is True
    replay = _verify(envelope, guard)
    assert replay.accepted is False
    assert replay.code == "replayed_instruction"
    assert replay.feature_id == "PET-02-08"


def test_concurrent_nonce_consumption_has_exactly_one_winner():
    guard = InMemoryReplayGuard()
    envelope = sign_instruction(_unsigned(), SECRET)
    with ThreadPoolExecutor(max_workers=12) as pool:
        decisions = list(pool.map(lambda _: _verify(envelope, guard), range(40)))
    assert sum(decision.accepted for decision in decisions) == 1
    assert sum(decision.code == "replayed_instruction" for decision in decisions) == 39


def test_database_migration_uses_atomic_unique_nonce_claim_and_rejects_expired_rows():
    sql = (Path(__file__).resolve().parents[1] / "sql" / "migrations" / "010_pet_instruction_replay_guard.sql").read_text(encoding="utf-8")
    assert "primary key (signer_id, nonce)" in sql
    assert "on conflict (signer_id, nonce) do nothing" in sql
    assert "p_expires_at <= now()" in sql
    assert "get diagnostics inserted = row_count" in sql


def test_postgres_guard_calls_single_atomic_database_function(monkeypatch):
    calls = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def execute(self, sql, params): calls.append((sql, params))
        def fetchone(self): return {"consume_pet_instruction_nonce": True}

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def cursor(self): return Cursor()
        def commit(self): calls.append(("commit", None))

    monkeypatch.setattr("ai_ops_center.db.connect", lambda local=False: Connection())
    accepted = PostgresReplayGuard(local=True).consume(
        "brain-gaming-pc",
        "nonce-00000001",
        "instruction-0001",
        "dev-laptop",
        NOW + timedelta(minutes=5),
        NOW,
        "a" * 64,
    )
    assert accepted is True
    assert calls[0][0] == "select consume_pet_instruction_nonce(%s, %s, %s, %s, %s, %s)"
    assert calls[0][1][-1] == "a" * 64
    assert calls[-1] == ("commit", None)


def test_invalid_signature_does_not_poison_replay_guard():
    guard = InMemoryReplayGuard()
    invalid = sign_instruction(_unsigned(), b"different-signing-secret-with-32-byte-minimum")
    assert _verify(invalid, guard).code == "invalid_signature"
    assert _verify(sign_instruction(_unsigned(), SECRET), guard).accepted is True


def test_naive_clock_is_rejected_by_verifier():
    envelope = sign_instruction(_unsigned(), SECRET)
    try:
        verify_instruction(
            envelope,
            expected_machine_id="dev-laptop",
            secret_for_signer=lambda _: SECRET,
            replay_guard=InMemoryReplayGuard(),
            now=datetime(2026, 7, 13, 18, 0),
        )
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive verification clocks must fail")
