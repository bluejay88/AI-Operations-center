import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "config" / "brain_feature_catalog_v1.json"
MIGRATION = ROOT / "sql" / "migrations" / "009_brain_feature_catalog.sql"


def catalog():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_brain_catalog_has_exact_unique_20_by_25_mapping():
    rows = catalog()["features"]
    assert len(rows) == 500
    assert rows[0]["feature_id"] == "BRAIN-01-01"
    assert rows[-1]["feature_id"] == "BRAIN-20-25"
    assert len({row["feature_id"] for row in rows}) == 500
    assert len({row["source_pet_feature_id"] for row in rows}) == 500
    assert len({(row["domain_no"], row["item_no"]) for row in rows}) == 500
    assert [row["source_order"] for row in rows] == list(range(1, 501))
    for row in rows:
        suffix = row["feature_id"].removeprefix("BRAIN-")
        assert row["source_pet_feature_id"] == f"PET-{suffix}"
        assert row["feature_id"] == f"BRAIN-{row['domain_no']:02d}-{row['item_no']:02d}"


def test_every_feature_has_auditable_acceptance_and_evidence_contract():
    rows = catalog()["features"]
    for row in rows:
        acceptance = row["acceptance_criteria"]
        evidence = row["evidence_requirements"]
        assert acceptance["criteria_id"] == f"{row['feature_id']}-AC-01"
        assert acceptance["prohibits_self_approval"] is True
        assert {"test_result", "audit_report", "brain_listener_receipt"} <= set(acceptance["required_evidence"])
        assert evidence["content_hash_required"] is True
        assert evidence["physical_brain_correlation_required"] is True
        assert row["implementation_contract"]["initial_implementation_status"] == "not_started"
        if row["sensitivity"] != "standard":
            assert "security" in acceptance["required_reviews"]


def test_brain_catalog_and_version_hashes_are_reproducible():
    payload = catalog()
    base_keys = (
        "feature_id", "source_pet_feature_id", "domain_no", "item_no", "source_order", "domain_title",
        "source_title", "sensitivity", "default_owner_role",
    )
    base = [{key: row[key] for key in base_keys} for row in payload["features"]]
    assert hashlib.sha256(canonical(base).encode()).hexdigest() == payload["catalog_sha256"]
    version_keys = ("implementation_contract", "acceptance_criteria", "acceptance_schema", "evidence_requirements", "failure_modes")
    for row in payload["features"]:
        version = {key: row[key] for key in version_keys}
        assert hashlib.sha256(canonical(version).encode()).hexdigest() == row["content_sha256"]


def test_migration_embeds_artifact_and_truthful_initial_status():
    sql = MIGRATION.read_text(encoding="utf-8")
    embedded = json.loads(re.search(r"\$catalog\$(.*?)\$catalog\$::jsonb", sql, re.S).group(1))
    assert embedded == catalog()["features"]
    assert all(row["implementation_contract"]["initial_implementation_status"] == "not_started" for row in embedded)
    initial = {"operational": 0, "gated": 0, "planned": len(embedded), "rejected": 0}
    assert initial == {"operational": 0, "gated": 0, "planned": 500, "rejected": 0}
    assert "count(*) filter(where implementation_status='implemented')" in sql
    assert "count(*) filter(where evidence_status='verified')" in sql


def test_migration_enforces_immutability_cas_idempotency_and_release_evidence():
    sql = MIGRATION.read_text(encoding="utf-8")
    required = (
        "on conflict (feature_id) do nothing", "on conflict (feature_id,version) do nothing",
        "on conflict (idempotency_key) do nothing", "Brain catalog definition mismatch",
        "Brain catalog version mismatch", "trg_brain_feature_definitions_immutable",
        "trg_brain_feature_versions_immutable", "trg_brain_feature_events_immutable",
        "trg_brain_feature_current_guard", "for update", "row version conflict",
        "Operational Brain feature requires implementation, verified evidence, release, and verification",
        "idx_brain_feature_state_status_updated", "idx_brain_feature_state_evidence",
        "idx_brain_feature_state_expiry", "idx_brain_feature_definitions_domain_order",
        "idx_brain_feature_events_feature_time",
    )
    for item in required:
        assert item in sql

