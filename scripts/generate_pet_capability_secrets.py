"""Generate a new, untracked PET directional-key generation.

The file is created exclusively and never printed. Copy its values into the
host secret store, register fingerprints, canary, then revoke the prior IDs.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
from datetime import UTC, datetime


MACHINES = ("brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".env.pet-secrets.next")
    parser.add_argument("--generation", default=datetime.now(UTC).strftime("v%Y%m%d%H%M%S"))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite {output}")
    lines = ["# Generated secret material. Never commit or paste into logs.", "PET_KEY_REGISTRY_REQUIRED=true"]
    for machine in MACHINES:
        suffix = machine.upper().replace("-", "_")
        dispatch = secrets.token_urlsafe(48)
        receipt = secrets.token_urlsafe(48)
        lines.extend((
            f"PET_DISPATCH_KEY_ID_{suffix}=dispatch:{machine}:{args.generation}",
            f"PET_RECEIPT_KEY_ID_{suffix}=receipt:{machine}:{args.generation}",
            f"PET_DISPATCH_SIGNING_KEY_{suffix}={dispatch}",
            f"PET_DISPATCH_VERIFY_KEY_{suffix}={dispatch}",
            f"PET_RECEIPT_SIGNING_KEY_{suffix}={receipt}",
            f"PET_RECEIPT_VERIFY_KEY_{suffix}={receipt}",
        ))
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    os.chmod(output, 0o600)
    print(f"Created {output.name} with restrictive permissions; contents were not displayed.")


if __name__ == "__main__":
    main()
