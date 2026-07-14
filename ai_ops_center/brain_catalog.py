from __future__ import annotations

from typing import Any

from .db import connect


def brain_feature_summary(local: bool = False) -> dict[str, Any]:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select coalesce(max(src.expected_total), 500) as expected_total,
                    count(*) filter (where c.state = 'O') as operational,
                    count(*) filter (where c.state = 'G') as approval_gated,
                    count(*) filter (where c.state = 'P') as planned,
                    count(*) filter (where c.state = 'R') as rejected,
                    count(*) filter (where c.implementation_status = 'implemented') as implemented,
                    count(*) filter (where c.evidence_status = 'verified') as evidence_verified,
                    count(*) filter (where c.release_status = 'operational') as released,
                    count(*) as total,
                    count(*) filter (where c.verification_expires_at is not null and c.verification_expires_at <= now()) as verification_expired,
                    (select count(*) from brain_feature_versions) as version_count,
                    (select count(*) from brain_feature_state_events) as event_count
                from brain_feature_state_current c
                cross join brain_feature_catalog_sources src
                """
            )
            row = dict(cur.fetchone() or {})
    expected = int(row.get("expected_total") or 500)
    total = int(row.get("total") or 0)
    return {
        "catalog_id": "brain-feature-catalog-v1",
        "operational": int(row.get("operational") or 0),
        "approval_gated": int(row.get("approval_gated") or 0),
        "planned": int(row.get("planned") or 0),
        "rejected": int(row.get("rejected") or 0),
        "implemented": int(row.get("implemented") or 0),
        "evidence_verified": int(row.get("evidence_verified") or 0),
        "released": int(row.get("released") or 0),
        "total": total,
        "expected_total": expected,
        "integrity": total == expected,
        "verification_expired": int(row.get("verification_expired") or 0),
        "version_count": int(row.get("version_count") or 0),
        "event_count": int(row.get("event_count") or 0),
        "counting_policy": "Only item-level, evidence-verified Brain capability states count; task totals are separate.",
    }


def brain_feature_detail(feature_id: str, local: bool = False) -> dict[str, Any] | None:
    normalized = str(feature_id or "").strip().upper()
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.feature_id, d.source_pet_feature_id, d.domain_no, d.item_no,
                       d.source_order, d.domain_title, d.source_title, d.sensitivity,
                       d.default_owner_role, c.feature_version, c.state,
                       c.implementation_status, c.evidence_status, c.release_status,
                       c.implementation_ref, c.release_id, c.last_verified_at,
                       c.verification_expires_at, c.row_version, c.updated_at
                from brain_feature_definitions d
                join brain_feature_state_current c on c.feature_id = d.feature_id
                where d.feature_id = %s
                """,
                (normalized,),
            )
            row = cur.fetchone()
    return dict(row) if row else None
