"""Independent transaction-only audit for migration 010; never persists rows/schema."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    connection = psycopg.connect(os.getenv("DATABASE_URL", "postgresql://aiops:aiops@localhost:5432/aiops"))
    try:
        with connection.cursor() as cursor:
            cursor.execute((ROOT / "sql/migrations/010_pet_instruction_replay_guard.sql").read_text(encoding="utf-8"))
            expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

            def consume(signer: str, nonce: str, instruction: str, target: str, expires_at: datetime) -> bool:
                cursor.execute(
                    "select consume_pet_instruction_nonce(%s,%s,%s,%s,%s)",
                    (signer, nonce, instruction, target, expires_at),
                )
                return bool(cursor.fetchone()[0])

            first = consume("review-brain", "review-nonce-0001", "review-instruction-0001", "dev-laptop", expiry)
            replay = consume("review-brain", "review-nonce-0001", "review-instruction-0001", "dev-laptop", expiry)
            other_signer = consume("review-brain-2", "review-nonce-0001", "review-instruction-0002", "dev-laptop", expiry)
            expired = consume(
                "review-brain", "review-nonce-expired", "review-instruction-expired", "dev-laptop",
                datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            cursor.execute("delete from pet_instruction_nonces where signer_id like 'review-brain%'")
            deletable_audit_rows = cursor.rowcount
            assert (first, replay, other_signer, expired) == (True, False, True, False)
            assert deletable_audit_rows == 2
            print(
                json.dumps(
                    {
                        "first_claim": first,
                        "same_signer_nonce_replay": replay,
                        "different_signer_same_nonce": other_signer,
                        "expired_claim": expired,
                        "audit_rows_deletable_by_application_role": deletable_audit_rows,
                        "transaction_rolled_back": True,
                    },
                    indent=2,
                )
            )
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    main()
