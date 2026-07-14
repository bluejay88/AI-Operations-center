from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ai_ops_center.db import connect
from ai_ops_center.pet_instruction_protocol import PostgresReplayGuard


def main() -> int:
    suffix = uuid4().hex
    nonce = f"audit-nonce-{suffix}"
    instruction_id = f"audit-instruction-{suffix}"
    now = datetime.now(UTC)
    guard = PostgresReplayGuard(local=True)

    def consume(_: int) -> bool:
        return guard.consume(
            "brain-gaming-pc", nonce, instruction_id, "dev-laptop", now + timedelta(minutes=5), now
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        concurrent_results = list(pool.map(consume, range(40)))

    expired = guard.consume(
        "brain-gaming-pc",
        f"expired-{nonce}",
        f"expired-{instruction_id}",
        "dev-laptop",
        now - timedelta(seconds=1),
        now,
    )
    second_signer = guard.consume(
        "canary-brain-signer", nonce, instruction_id, "dev-laptop", now + timedelta(minutes=5), now
    )
    report = {
        "concurrent_attempts": len(concurrent_results),
        "atomic_winners": sum(concurrent_results),
        "replays_rejected": len(concurrent_results) - sum(concurrent_results),
        "expired_claim_accepted": expired,
        "same_nonce_distinct_signer_accepted": second_signer,
    }
    report["passed"] = (
        report["atomic_winners"] == 1
        and report["replays_rejected"] == 39
        and report["expired_claim_accepted"] is False
        and report["same_nonce_distinct_signer_accepted"] is True
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    with connect(local=True) as conn:
        with conn.cursor() as cur:
            cur.execute("delete from pet_instruction_nonces where nonce in (%s, %s)", (nonce, f"expired-{nonce}"))
        conn.commit()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
