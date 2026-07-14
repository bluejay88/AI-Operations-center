from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping


RUBRIC_DIMENSIONS = (
    "requirements",
    "security",
    "reliability",
    "usability_accessibility",
    "auditability",
    "rollback",
)

MANIFEST_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
BATCH_POLICIES = {
    "PET-02A": {
        "feature_ids": ("PET-02-04", "PET-02-05", "PET-02-06", "PET-02-07", "PET-02-08"),
        "requires_peer_response": True,
        "review_roles": frozenset({"quality", "security"}),
    }
}
ACTION_POLICIES = {
    "browser_navigation": {"approval_required": True},
    "external_navigation": {"approval_required": True},
    "remote_control": {"approval_required": True},
    "music_control": {"approval_required": False},
    "local_model": {"approval_required": False},
}


def evaluate_capability_batch(
    submission: Mapping[str, Any],
    *,
    repository_root: Path,
    catalog_path: Path | None = None,
    evidence_resolver: Callable[[str], Mapping[str, Any]] | None = None,
    local: bool = False,
) -> dict[str, Any]:
    """Evaluate immutable authoritative evidence without changing a catalog state.

    The caller supplies only a manifest hash. Feature scope, artifacts, tests,
    physical references, reviews, rubric scores, and the Brain decision are all
    loaded from the content-addressed manifest and correlated database rows.
    """
    root = repository_root.resolve()
    catalog_file = catalog_path or root / "config" / "pet_feature_catalog_v1.json"
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    definitions = {row["feature_id"]: row for row in catalog["features"]}

    requested_hash = str(submission.get("manifest_sha256") or "").lower()
    resolution_error: str | None = None
    resolved: Mapping[str, Any] = {}
    if MANIFEST_HASH_PATTERN.fullmatch(requested_hash):
        try:
            resolver = evidence_resolver or (lambda digest: _resolve_authoritative_evidence(digest, local=local))
            resolved = resolver(requested_hash) or {}
        except Exception:
            # Database outages and malformed resolver results must hold every
            # authority-dependent gate without leaking connection details.
            resolution_error = "authoritative_evidence_unavailable"

    manifest = resolved.get("manifest") if isinstance(resolved, Mapping) else None
    manifest = manifest if isinstance(manifest, Mapping) else {}
    manifest_ok = bool(manifest) and _manifest_sha256(manifest) == requested_hash
    batch_id = str(manifest.get("batch_id") or "") if manifest_ok else ""
    policy = BATCH_POLICIES.get(batch_id)
    feature_ids = [str(value) for value in manifest.get("feature_ids") or []] if manifest_ok else []
    catalog_ok = bool(policy) and tuple(feature_ids) == tuple(policy["feature_ids"])
    catalog_ok = catalog_ok and all(feature_id in definitions for feature_id in feature_ids)

    artifacts_ok, artifact_results = _verify_artifacts(list(manifest.get("artifacts") or []), root)
    tests = manifest.get("tests") if isinstance(manifest.get("tests"), Mapping) else {}
    report = tests.get("report") if isinstance(tests.get("report"), Mapping) else {}
    report_ok, report_results = _verify_artifacts([report] if report else [], root)
    tests_ok = (
        _positive_int(tests.get("passed"))
        and _nonnegative_int(tests.get("failed"))
        and int(tests["failed"]) == 0
        and report_ok
    )

    refs = manifest.get("evidence_refs") if isinstance(manifest.get("evidence_refs"), Mapping) else {}
    producer = str(refs.get("producer_machine_id") or "")
    task = _mapping(resolved.get("task"))
    listener = _mapping(resolved.get("listener"))
    peer = _mapping(resolved.get("peer"))
    task_meta = _mapping(task.get("metadata"))
    listener_meta = _mapping(listener.get("metadata"))
    peer_meta = _mapping(peer.get("response_metadata"))

    task_ok = (
        _same_positive_id(task, refs.get("task_id"))
        and task.get("status") == "completed"
        and task.get("claimed_by_machine") == producer
        and bool(task.get("completed_at"))
        and task_meta.get("capability_manifest_sha256") == requested_hash
    )
    listener_ok = (
        _same_positive_id(listener, refs.get("listener_event_id"))
        and listener.get("source_type") == "machine"
        and listener.get("source_id") == producer
        and listener_meta.get("capability_manifest_sha256") == requested_hash
        and listener_meta.get("task_id") == refs.get("task_id")
    )
    peer_required = bool(policy and policy["requires_peer_response"])
    peer_ok = (
        _same_positive_id(peer, refs.get("peer_request_id"))
        and peer.get("task_id") == refs.get("task_id")
        and peer.get("status") == "fulfilled"
        and peer.get("to_machine_id") == producer
        and peer.get("responder_machine_id") == producer
        and bool(peer.get("responded_at"))
        and peer_meta.get("capability_manifest_sha256") == requested_hash
    )
    physical_ok = manifest_ok and bool(producer) and task_ok and listener_ok and (peer_ok if peer_required else True)

    owner = str(manifest.get("implementation_owner") or "").strip()
    review_rows = [row for row in (resolved.get("reviews") or []) if isinstance(row, Mapping)]
    latest_by_role: dict[str, Mapping[str, Any]] = {}
    for row in review_rows:
        role = str(row.get("reviewer_role") or "")
        if role:
            latest_by_role[role] = row
    accepted_reviews = [
        row
        for row in latest_by_role.values()
        if row.get("manifest_sha256") == requested_hash
        and row.get("decision") == "accepted"
        and str(row.get("reviewer_id") or "").strip()
        and str(row.get("reviewer_id")) != owner
    ]
    review_roles = {str(row.get("reviewer_role") or "") for row in accepted_reviews}
    required_review_roles = set(policy["review_roles"]) if policy else {"quality", "security"}
    reviewer_ids = {str(row.get("reviewer_id")) for row in accepted_reviews}
    independent_ok = (
        bool(owner)
        and required_review_roles.issubset(review_roles)
        and len(reviewer_ids) >= len(required_review_roles)
    )

    rubric_scores = {
        dimension: min((_score(_mapping(row.get("rubric")).get(dimension)) for row in accepted_reviews), default=0)
        for dimension in RUBRIC_DIMENSIONS
    }
    rubric_scores_ok = all(score >= 80 for score in rubric_scores.values())
    weighted_score = round(sum(rubric_scores.values()) / len(RUBRIC_DIMENSIONS), 2)
    rubric_ok = independent_ok and rubric_scores_ok and weighted_score >= 90

    rollback_ok = bool(str(manifest.get("rollback_plan") or "").strip())
    brain_decision = _mapping(resolved.get("brain_decision"))
    brain_ok = (
        brain_decision.get("manifest_sha256") == requested_hash
        and brain_decision.get("decision") in {"release", "canary_passed"}
        and brain_decision.get("actor") == "brain-gaming-pc"
    )

    action_contracts = [item for item in (manifest.get("actions") or []) if isinstance(item, Mapping)]
    action_receipts = {
        str(row.get("action_key")): row
        for row in (resolved.get("action_receipts") or [])
        if isinstance(row, Mapping) and str(row.get("action_key") or "")
    }
    approvals = {
        row.get("id"): row
        for row in (resolved.get("action_approvals") or [])
        if isinstance(row, Mapping) and _positive_int(row.get("id"))
    }
    action_results = [
        _evaluate_action_contract(action, action_receipts.get(str(action.get("action_key") or "")), approvals, requested_hash)
        for action in action_contracts
    ]
    actions_shape_ok = isinstance(manifest.get("actions", []), list) and len(action_contracts) == len(manifest.get("actions", []))
    audited_actions_ok = manifest_ok and actions_shape_ok and all(item["valid"] for item in action_results)

    gates = {
        "content_addressed_manifest": manifest_ok,
        "catalog_contract": catalog_ok,
        "artifact_integrity": artifacts_ok,
        "tests": tests_ok,
        "physical_machine_evidence": physical_ok,
        "independent_review": independent_ok,
        "rubric": rubric_ok,
        "rollback": rollback_ok,
        "brain_release_decision": brain_ok,
        "audited_machine_actions": audited_actions_ok,
    }
    implementation_verified = all(
        gates[key]
        for key in ("content_addressed_manifest", "catalog_contract", "artifact_integrity", "tests", "rollback")
    )
    release_candidate = all(gates.values())
    if not implementation_verified:
        phase = "implementation_unverified"
    elif not physical_ok:
        phase = "awaiting_physical_evidence"
    elif not independent_ok or not rubric_ok:
        phase = "awaiting_independent_review"
    elif not brain_ok:
        phase = "awaiting_brain_decision"
    else:
        phase = "release_candidate"

    return {
        "manifest_sha256": requested_hash or None,
        "batch_id": batch_id or None,
        "feature_ids": feature_ids,
        "source_titles": {key: definitions[key]["source_title"] for key in feature_ids if key in definitions},
        "gates": gates,
        "failed_gates": [key for key, passed in gates.items() if not passed],
        "artifact_results": artifact_results,
        "test_report_results": report_results,
        "authoritative_resolution": {
            "manifest": manifest_ok,
            "task": task_ok,
            "listener": listener_ok,
            "peer": peer_ok,
            "review_count": len(accepted_reviews),
            "brain_decision": brain_ok,
            "action_receipts": sum(1 for item in action_results if item["receipt_correlated"]),
            "error": resolution_error,
        },
        "action_results": action_results,
        "rubric_scores": rubric_scores,
        "weighted_score": weighted_score,
        "implementation_verified": implementation_verified,
        "release_candidate": release_candidate,
        "phase": phase,
        "current_ledger_state": "P",
        "requested_transition": "O" if release_candidate else None,
        "ledger_transition_authorized": False,
        "counting_note": "Evidence evaluation never changes the ledger; caller assertions outside the resolved manifest are ignored.",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Return the stable content address used by certification records."""
    return _manifest_sha256(manifest)


def _manifest_sha256(manifest: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return ""
    return hashlib.sha256(encoded).hexdigest()


def _resolve_authoritative_evidence(manifest_hash: str, *, local: bool) -> dict[str, Any]:
    from .db import connect

    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select manifest from pet_capability_manifests where manifest_sha256 = %s", (manifest_hash,))
            row = cur.fetchone()
            if not row:
                return {}
            manifest = _mapping(row["manifest"])
            refs = _mapping(manifest.get("evidence_refs"))

            task = _fetch_one(cur, "select * from tasks where id = %s", refs.get("task_id"))
            listener = _fetch_one(cur, "select * from listener_events where id = %s", refs.get("listener_event_id"))
            peer = _fetch_one(cur, "select * from peer_requests where id = %s", refs.get("peer_request_id"))
            cur.execute(
                "select * from pet_capability_reviews where manifest_sha256 = %s order by created_at, id",
                (manifest_hash,),
            )
            reviews = [dict(item) for item in cur.fetchall()]
            cur.execute(
                "select * from pet_capability_action_receipts where manifest_sha256 = %s order by created_at, id",
                (manifest_hash,),
            )
            action_receipts = [dict(item) for item in cur.fetchall()]
            approval_ids = [row["approval_request_id"] for row in action_receipts if row.get("approval_request_id")]
            action_approvals: list[dict[str, Any]] = []
            if approval_ids:
                cur.execute("select * from approval_requests where id = any(%s)", (approval_ids,))
                action_approvals = [dict(item) for item in cur.fetchall()]
            brain_decision = _fetch_one(
                cur,
                "select * from pet_capability_brain_decisions where manifest_sha256 = %s order by created_at desc, id desc limit 1",
                manifest_hash,
                require_positive_int=False,
            )
    return {
        "manifest": manifest,
        "task": task,
        "listener": listener,
        "peer": peer,
        "reviews": reviews,
        "brain_decision": brain_decision,
        "action_receipts": action_receipts,
        "action_approvals": action_approvals,
    }


def _evaluate_action_contract(
    action: Mapping[str, Any],
    receipt_value: Any,
    approvals: Mapping[Any, Mapping[str, Any]],
    manifest_hash: str,
) -> dict[str, Any]:
    action_key = str(action.get("action_key") or "")
    action_type = str(action.get("action_type") or "")
    target_machine_id = str(action.get("target_machine_id") or "")
    policy = ACTION_POLICIES.get(action_type)
    approval_required = bool(
        policy
        and (
            policy["approval_required"]
            or action.get("remote_control") is True
            or action.get("external_navigation") is True
        )
    )
    receipt = _mapping(receipt_value)
    receipt_correlated = bool(
        policy
        and action_key
        and target_machine_id
        and receipt.get("manifest_sha256") == manifest_hash
        and receipt.get("action_key") == action_key
        and receipt.get("action_type") == action_type
        and receipt.get("target_machine_id") == target_machine_id
        and receipt.get("status") == "completed"
        and receipt.get("task_id") == action.get("task_id")
        and receipt.get("listener_event_id") == action.get("listener_event_id")
        and MANIFEST_HASH_PATTERN.fullmatch(str(receipt.get("result_sha256") or "")) is not None
    )
    approval = _mapping(approvals.get(receipt.get("approval_request_id")))
    approval_meta = _mapping(approval.get("metadata"))
    approval_ok = not approval_required or bool(
        _positive_int(receipt.get("approval_request_id"))
        and approval.get("status") in {"approved", "deployed"}
        and bool(approval.get("approved_at"))
        and approval_meta.get("capability_manifest_sha256") == manifest_hash
        and approval_meta.get("action_key") == action_key
    )
    return {
        "action_key": action_key,
        "action_type": action_type,
        "target_machine_id": target_machine_id,
        "approval_required": approval_required,
        "receipt_correlated": receipt_correlated,
        "approval_correlated": approval_ok,
        "valid": receipt_correlated and approval_ok,
    }


def _fetch_one(cur: Any, sql: str, value: Any, *, require_positive_int: bool = True) -> dict[str, Any]:
    if require_positive_int and not _positive_int(value):
        return {}
    if value is None or value == "":
        return {}
    cur.execute(sql, (value,))
    row = cur.fetchone()
    return dict(row) if row else {}


def _verify_artifacts(artifacts: list[Any], root: Path) -> tuple[bool, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            results.append({"valid": False, "reason": "artifact must be an object"})
            continue
        relative = str(artifact.get("path") or "")
        expected = str(artifact.get("sha256") or "").lower()
        candidate = (root / relative).resolve()
        inside_root = candidate == root or root in candidate.parents
        exists = inside_root and candidate.is_file()
        actual = sha256_file(candidate) if exists else None
        valid = exists and MANIFEST_HASH_PATTERN.fullmatch(expected) is not None and actual == expected
        results.append({"path": relative, "sha256": actual, "valid": valid})
    return bool(results) and all(item["valid"] for item in results), results


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _same_positive_id(row: Mapping[str, Any], expected: Any) -> bool:
    return _positive_int(expected) and row.get("id") == expected


def _positive_int(value: Any) -> bool:
    return _nonnegative_int(value) and int(value) > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _score(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100 else 0
