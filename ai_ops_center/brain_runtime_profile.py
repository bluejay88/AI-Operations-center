from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .brain_identity import BrainIdentityProfile, DeviceIdentityRegistry
from .brain_personality_policy import FEATURE_IDS as STYLE_FEATURE_IDS
from .brain_personality_policy import LaptopPersonalityPolicy
from .config import load_machines
from .db import ROOT, connect


IDENTITY_FEATURE_IDS = tuple(f"BRAIN-01-{item:02d}" for item in range(1, 6))
RUNTIME_FEATURE_IDS = IDENTITY_FEATURE_IDS + STYLE_FEATURE_IDS
PROFILE_VERSION = "brain-runtime-profile-v1"
MACHINES_PATH = Path(ROOT) / "config" / "machines.yaml"


class PostgresDeviceIdentityRegistry(DeviceIdentityRegistry):
    """Durable atomic registry available only to explicitly approved callers."""

    def __init__(self, *, actor: str, approval_ref: str, mutation_authorized: bool, local: bool = False) -> None:
        self.actor = actor.strip()
        self.approval_ref = approval_ref.strip()
        self.mutation_authorized = mutation_authorized
        self.local = local
        if not self.actor or not self.approval_ref:
            raise ValueError("actor and approval_ref are required for identity reservation")

    def reserve(self, device_id: str) -> bool:
        if not self.mutation_authorized:
            raise PermissionError("device identity mutation requires governed approval")
        profile = BrainIdentityProfile(device_id=device_id)
        with connect(local=self.local) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into brain_device_identity_reservations
                        (device_id, identity_fingerprint, reserved_by, approval_ref)
                    values (%s, %s, %s, %s)
                    on conflict (device_id) do nothing
                    returning device_id
                    """,
                    (profile.device_id, profile.fingerprint(), self.actor, self.approval_ref),
                )
                created = cur.fetchone() is not None
            conn.commit()
        return created

    def release(self, device_id: str) -> bool:
        raise PermissionError("identity reservations are append-only; governed decommission is not implemented")


def runtime_profile(local: bool = False) -> dict[str, Any]:
    identity = BrainIdentityProfile()
    inventory_version = _inventory_version()
    personalities = LaptopPersonalityPolicy.default(inventory_version=inventory_version)
    reservation = _registered_device(identity.device_id, local=local)
    return {
        "profile_version": PROFILE_VERSION,
        "feature_ids": list(RUNTIME_FEATURE_IDS),
        "ledger_state": "P",
        "identity": identity.public_payload(),
        "laptop_personalities": personalities.public_payload(),
        "durable_identity": reservation,
        "governance": {
            "read_only_api": True,
            "mutation_endpoint_exposed": False,
            "personality_changes_authorized": False,
            "ledger_transition_authorized": False,
        },
    }


def laptop_runtime_profile(machine_id: str) -> dict[str, Any] | None:
    inventory_version = _inventory_version()
    policy = LaptopPersonalityPolicy.default(inventory_version=inventory_version)
    try:
        speaking = policy.for_laptop(machine_id)
    except ValueError:
        return None
    machine = next((item for item in load_machines() if item.get("id") == machine_id), None)
    if machine is None:
        return None
    return {
        "machine_id": machine_id,
        "machine_name": machine.get("name"),
        "role": machine.get("role"),
        "inventory_version": inventory_version,
        "speaking_profile": asdict(speaking),
        "profile_fingerprint": speaking.fingerprint(),
        "feature_ids": list(STYLE_FEATURE_IDS),
        "ledger_state": "P",
        "mutation_authorized": False,
    }


def runtime_profile_readiness(local: bool = False) -> dict[str, Any]:
    profile = runtime_profile(local=local)
    configured_laptops = {item["id"] for item in load_machines() if item["id"].endswith("-laptop")}
    profiled_laptops = set(profile["laptop_personalities"]["profiles"])
    checks = {
        "exact_feature_batch": tuple(profile["feature_ids"]) == RUNTIME_FEATURE_IDS,
        "durable_identity_reserved": bool(profile["durable_identity"]),
        "inventory_matches_configuration": configured_laptops == profiled_laptops,
        "read_only_api": profile["governance"]["read_only_api"],
        "no_mutation_endpoint": not profile["governance"]["mutation_endpoint_exposed"],
    }
    return {
        "profile_version": PROFILE_VERSION,
        "checks": checks,
        "integration_ready": all(checks.values()),
        "operational_certified": False,
        "ledger_state": "P",
        "remaining_gates": [
            "physical_brain_correlation",
            "brain_listener_receipt",
            "content_addressed_evidence_manifest",
            "independent_release_decision",
            "operational_release_id",
            "fresh_verification_timestamp",
            "governed_ledger_transition",
        ],
    }


def _inventory_version() -> str:
    normalized = MACHINES_PATH.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return f"machines.yaml:sha256:{hashlib.sha256(normalized).hexdigest()}"


def _registered_device(device_id: str, local: bool = False) -> dict[str, Any] | None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select device_id, identity_fingerprint, reserved_by, approval_ref, reserved_at
                from brain_device_identity_reservations
                where device_id = %s
                """,
                (device_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else None
