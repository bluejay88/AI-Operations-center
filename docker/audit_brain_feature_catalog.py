"""Transaction-only database audit for migration 009 (always rolls back)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "postgresql://aiops:aiops@localhost:5432/aiops")
    connection = psycopg.connect(dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute((ROOT / "sql/migrations/009_brain_feature_catalog.sql").read_text(encoding="utf-8"))
            cursor.execute("select * from seed_brain_feature_catalog_v1()")
            second_seed = cursor.fetchone()
            cursor.execute("select * from brain_feature_state_summary")
            summary = cursor.fetchone()
            cursor.execute("select count(*) from brain_feature_versions where version = 1")
            versions = cursor.fetchone()[0]
            cursor.execute("select count(*) from brain_feature_state_events where actor = 'brain-feature-catalog-v1'")
            events = cursor.fetchone()[0]
            cursor.execute(
                "select count(*) from brain_feature_state_current "
                "where implementation_status = 'not_started' and evidence_status = 'none' and release_status = 'unreleased'"
            )
            truthful_initial = cursor.fetchone()[0]
            result = {
                "second_seed_inserted": list(second_seed),
                "summary": {
                    "operational": summary[0], "gated": summary[1], "planned": summary[2], "rejected": summary[3],
                    "total": summary[4], "expected_total": summary[5], "integrity": summary[6],
                    "implemented": summary[7], "evidence_verified": summary[8], "released_operational": summary[9],
                },
                "versions": versions,
                "initial_events": events,
                "truthful_not_started_none_unreleased": truthful_initial,
                "transaction_rolled_back": True,
            }
            assert second_seed == (0, 0, 0, 0)
            assert summary == (0, 0, 500, 0, 500, 500, True, 0, 0, 0)
            assert versions == events == truthful_initial == 500
            print(json.dumps(result, indent=2))
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
