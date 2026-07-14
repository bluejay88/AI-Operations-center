from __future__ import annotations

from typing import Any

from .db import connect


def pet_feature_summary(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    coalesce(max(src.expected_total), 500) as expected_total,
                    count(*) filter (where c.state = 'O') as operational,
                    count(*) filter (where c.state = 'G') as approval_gated,
                    count(*) filter (where c.state = 'P') as planned,
                    count(*) filter (where c.state = 'R') as rejected,
                    count(*) as total,
                    count(*) filter (
                        where c.verification_expires_at is not null
                          and c.verification_expires_at <= now()
                    ) as verification_expired,
                    (select count(*) from pet_feature_versions) as version_count,
                    (select count(*) from pet_feature_state_events) as event_count
                from pet_feature_state_current c
                cross join pet_feature_catalog_sources src
                """
            )
            row = dict(cur.fetchone() or {})
    expected = int(row.get("expected_total") or 500)
    total = int(row.get("total") or 0)
    return {
        "catalog_id": "pet-feature-catalog-v1",
        "operational": int(row.get("operational") or 0),
        "approval_gated": int(row.get("approval_gated") or 0),
        "planned": int(row.get("planned") or 0),
        "rejected": int(row.get("rejected") or 0),
        "total": total,
        "expected_total": expected,
        "integrity": total == expected,
        "verification_expired": int(row.get("verification_expired") or 0),
        "version_count": int(row.get("version_count") or 0),
        "event_count": int(row.get("event_count") or 0),
        "counting_policy": "Only item-level, Brain-reviewed catalog states count; task totals are separate.",
    }


def pet_feature_detail(feature_id: str, local: bool = False) -> dict[str, Any] | None:
    normalized = str(feature_id or "").strip().upper()
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select definitions.feature_id, definitions.domain_no, definitions.item_no,
                       definitions.source_order, definitions.source_title, definitions.sensitivity,
                       definitions.default_owner_pet_id, c.feature_version, c.state,
                       c.release_id, c.last_verified_at, c.verification_expires_at,
                       c.row_version, c.updated_at
                from pet_feature_definitions definitions
                join pet_feature_state_current c on c.feature_id = definitions.feature_id
                where definitions.feature_id = %s
                """,
                (normalized,),
            )
            row = cur.fetchone()
    return dict(row) if row else None
