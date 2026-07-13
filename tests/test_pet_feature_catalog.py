import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "config" / "pet_feature_catalog_v1.json"
MIGRATION = ROOT / "sql" / "migrations" / "007_pet_feature_catalog.sql"


def _catalog():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_catalog_is_exactly_20_by_25_with_stable_ids_and_titles():
    catalog = _catalog()
    rows = catalog["features"]
    assert catalog["expected_total"] == 500
    assert len(rows) == 20 * 25 == 500
    assert rows[0]["feature_id"] == "PET-01-01"
    assert rows[-1]["feature_id"] == "PET-20-25"
    assert [row["source_order"] for row in rows] == list(range(1, 501))
    assert len({row["feature_id"] for row in rows}) == 500
    assert len({(row["domain_no"], row["item_no"]) for row in rows}) == 500
    assert all(row["feature_id"] == f"PET-{row['domain_no']:02d}-{row['item_no']:02d}" for row in rows)
    assert next(row for row in rows if row["feature_id"] == "PET-02-17")["source_title"] == "Request another PET’s assistance."


def test_catalog_hashes_and_version_contract_hashes_are_deterministic():
    catalog = _catalog()
    base_keys = {
        "feature_id", "domain_no", "item_no", "source_order", "source_title", "sensitivity", "default_owner_pet_id"
    }
    base_rows = [{key: row[key] for key in base_keys} for row in catalog["features"]]
    assert hashlib.sha256(_canonical(base_rows).encode()).hexdigest() == catalog["catalog_sha256"]
    for row in catalog["features"]:
        content = {key: row[key] for key in ("contract", "acceptance_schema", "permissions", "failure_modes")}
        assert hashlib.sha256(_canonical(content).encode()).hexdigest() == row["content_sha256"]


def test_migration_embeds_same_catalog_and_initial_ledger_totals():
    sql = MIGRATION.read_text(encoding="utf-8")
    embedded = json.loads(re.search(r"\$catalog\$(.*?)\$catalog\$::jsonb", sql, re.S).group(1))
    assert embedded == _catalog()["features"]
    initial = {"O": 0, "G": 0, "P": len(embedded), "R": 0}
    assert initial == {"O": 0, "G": 0, "P": 500, "R": 0}
    assert "500::integer as expected_total" in sql
    assert "(count(*) = 500)::boolean as integrity" in sql


def test_migration_has_idempotency_immutability_constraints_and_indexes():
    sql = MIGRATION.read_text(encoding="utf-8")
    required = [
        "on conflict (catalog_id) do nothing",
        "on conflict (feature_id) do nothing",
        "on conflict (feature_id, version) do nothing",
        "on conflict (idempotency_key) do nothing",
        "PET catalog definition mismatch; immutable source was altered",
        "PET catalog version mismatch; immutable contract was altered",
        "unique (domain_no, item_no)",
        "unique (feature_id, version)",
        "idempotency_key text not null unique",
        "trg_pet_feature_definitions_immutable",
        "trg_pet_feature_versions_immutable",
        "trg_pet_feature_events_immutable",
        "trg_pet_feature_current_guard",
        "idx_pet_feature_state_state_updated",
        "idx_pet_feature_state_verification_expiry",
        "idx_pet_feature_definitions_owner_domain",
        "idx_pet_feature_state_events_feature_time",
        "for update",
        "row version conflict",
    ]
    for token in required:
        assert token in sql
