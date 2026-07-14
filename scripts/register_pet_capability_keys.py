"""Register PET key fingerprints from the process environment.

Secret values are never printed or stored in PostgreSQL. Existing matching
registrations are accepted, while mismatches and overlapping active keys fail
closed so this helper cannot silently rotate production authority.
"""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta

from ai_ops_center.db import connect
from ai_ops_center.pet_machine_capabilities import MACHINE_PETS, register_machine_capability_key


def _value(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    now = datetime.now(UTC)
    registered = 0
    unchanged = 0
    for machine_id in MACHINE_PETS:
        suffix = machine_id.upper().replace("-", "_")
        for direction in ("dispatch", "receipt"):
            key_id = _value(f"PET_{direction.upper()}_KEY_ID_{suffix}")
            secret = _value(f"PET_{direction.upper()}_SIGNING_KEY_{suffix}").encode()
            if len(secret) < 32:
                raise RuntimeError(f"{direction} key for {machine_id} is too short")
            fingerprint = hashlib.sha256(secret).hexdigest()
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "select machine_id,direction,secret_fingerprint_sha256,revoked_at,not_after "
                        "from pet_machine_capability_keys where key_id=%s",
                        (key_id,),
                    )
                    row = cur.fetchone()
            if row:
                if (
                    row["machine_id"] != machine_id
                    or row["direction"] != direction
                    or row["secret_fingerprint_sha256"] != fingerprint
                    or row["revoked_at"] is not None
                    or row["not_after"] <= now
                ):
                    raise RuntimeError(f"existing registry entry {key_id} is not an active exact match")
                unchanged += 1
                continue
            register_machine_capability_key(
                key_id=key_id,
                machine_id=machine_id,
                direction=direction,
                secret=secret,
                actor="security-bootstrap",
                not_before=now - timedelta(minutes=5),
                not_after=now + timedelta(days=90),
            )
            registered += 1
    print(f"PET key registry ready: {registered} registered, {unchanged} unchanged; no secrets displayed.")


if __name__ == "__main__":
    main()
