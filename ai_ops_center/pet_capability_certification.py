from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


RUBRIC_DIMENSIONS = (
    "requirements",
    "security",
    "reliability",
    "usability_accessibility",
    "auditability",
    "rollback",
)


def evaluate_capability_batch(
    submission: Mapping[str, Any],
    *,
    repository_root: Path,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate a feature batch without authorizing a catalog state transition."""
    root = repository_root.resolve()
    catalog_file = catalog_path or root / "config" / "pet_feature_catalog_v1.json"
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    definitions = {row["feature_id"]: row for row in catalog["features"]}
    feature_ids = [str(value) for value in submission.get("feature_ids") or []]

    catalog_ok = bool(feature_ids) and len(feature_ids) <= 5 and len(feature_ids) == len(set(feature_ids))
    catalog_ok = catalog_ok and all(feature_id in definitions for feature_id in feature_ids)
    artifacts_ok, artifact_results = _verify_artifacts(submission.get("artifacts") or [], root)
    tests = submission.get("tests") or {}
    tests_ok = (
        _positive_int(tests.get("passed"))
        and _nonnegative_int(tests.get("failed"))
        and int(tests["failed"]) == 0
        and bool(str(tests.get("report") or "").strip())
    )
    physical = submission.get("physical_evidence") or {}
    physical_ok = all(_positive_int(physical.get(key)) for key in ("task_id", "listener_event_id"))
    if submission.get("requires_peer_response", True):
        physical_ok = physical_ok and _positive_int(physical.get("peer_request_id"))
    physical_ok = physical_ok and bool(str(physical.get("producer_machine_id") or "").strip())

    owner = str(submission.get("implementation_owner") or "").strip()
    reviewers = {str(item).strip() for item in submission.get("reviewed_by") or [] if str(item).strip()}
    independent_ok = bool(owner) and owner not in reviewers and {"rubric-auditor", "security-monitor"}.issubset(reviewers)
    rubric = submission.get("rubric") or {}
    rubric_scores_ok = all(_score(rubric.get(key)) >= 80 for key in RUBRIC_DIMENSIONS)
    weighted_score = round(sum(_score(rubric.get(key)) for key in RUBRIC_DIMENSIONS) / len(RUBRIC_DIMENSIONS), 2)
    rubric_ok = rubric_scores_ok and weighted_score >= 90
    rollback_ok = bool(str(submission.get("rollback_plan") or "").strip())
    brain_decision = str(submission.get("brain_decision") or "hold").lower()

    gates = {
        "catalog_contract": catalog_ok,
        "artifact_integrity": artifacts_ok,
        "tests": tests_ok,
        "physical_machine_evidence": physical_ok,
        "independent_review": independent_ok,
        "rubric": rubric_ok,
        "rollback": rollback_ok,
        "brain_release_decision": brain_decision in {"release", "canary_passed"},
    }
    implementation_verified = all(gates[key] for key in ("catalog_contract", "artifact_integrity", "tests", "rollback"))
    release_candidate = all(gates.values())
    if not implementation_verified:
        phase = "implementation_unverified"
    elif not physical_ok:
        phase = "awaiting_physical_evidence"
    elif not independent_ok or not rubric_ok:
        phase = "awaiting_independent_review"
    elif not gates["brain_release_decision"]:
        phase = "awaiting_brain_decision"
    else:
        phase = "release_candidate"

    return {
        "feature_ids": feature_ids,
        "source_titles": {key: definitions[key]["source_title"] for key in feature_ids if key in definitions},
        "gates": gates,
        "failed_gates": [key for key, passed in gates.items() if not passed],
        "artifact_results": artifact_results,
        "weighted_score": weighted_score,
        "implementation_verified": implementation_verified,
        "release_candidate": release_candidate,
        "phase": phase,
        "current_ledger_state": "P",
        "requested_transition": "O" if release_candidate else None,
        "ledger_transition_authorized": False,
        "counting_note": "This evaluator produces evidence only; Brain must append the release decision and transition the ledger transactionally.",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        valid = exists and len(expected) == 64 and actual == expected
        results.append({"path": relative, "sha256": actual, "valid": valid})
    return bool(results) and all(item["valid"] for item in results), results


def _positive_int(value: Any) -> bool:
    return _nonnegative_int(value) and int(value) > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _score(value: Any) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100 else 0
