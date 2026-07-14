from __future__ import annotations

import json
import hashlib
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ai_ops_center.db import connect
from ai_ops_center.pet_instruction_protocol import PostgresReplayGuard


def _consume_in_process(args: tuple[str, str, str, datetime, datetime, str]) -> bool:
    nonce, instruction_id, target_machine_id, expires_at, now, envelope_sha256 = args
    return PostgresReplayGuard(local=True).consume(
        "brain-gaming-pc",
        nonce,
        instruction_id,
        target_machine_id,
        expires_at,
        now,
        envelope_sha256,
    )


def main() -> int:
    suffix = uuid4().hex
    nonce = f"audit-nonce-{suffix}"
    instruction_id = f"audit-instruction-{suffix}"
    now = datetime.now(UTC)
    guard = PostgresReplayGuard(local=True)
    envelope_sha256 = hashlib.sha256(f"audit:{suffix}".encode("utf-8")).hexdigest()

    def consume(_: int) -> bool:
        return guard.consume(
            "brain-gaming-pc", nonce, instruction_id, "dev-laptop", now + timedelta(minutes=5), now, envelope_sha256
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        concurrent_results = list(pool.map(consume, range(40)))

    process_nonce = f"process-{nonce}"
    process_instruction_id = f"process-{instruction_id}"
    process_args = (
        process_nonce,
        process_instruction_id,
        "dev-laptop",
        now + timedelta(minutes=5),
        now,
        hashlib.sha256(f"process:{suffix}".encode("utf-8")).hexdigest(),
    )
    with ProcessPoolExecutor(max_workers=4) as pool:
        process_results = list(pool.map(_consume_in_process, [process_args] * 12))

    expired = guard.consume(
        "brain-gaming-pc",
        f"expired-{nonce}",
        f"expired-{instruction_id}",
        "dev-laptop",
        now - timedelta(seconds=1),
        now,
        hashlib.sha256(f"expired:{suffix}".encode("utf-8")).hexdigest(),
    )
    second_signer = guard.consume(
        "canary-brain-signer",
        nonce,
        instruction_id,
        "dev-laptop",
        now + timedelta(minutes=5),
        now,
        envelope_sha256,
    )
    restart_replay = guard.consume(
        "brain-gaming-pc",
        nonce,
        instruction_id,
        "dev-laptop",
        now + timedelta(minutes=5),
        now,
        envelope_sha256,
    )

    rollback_nonce = f"rollback-{nonce}"
    with connect(local=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select consume_pet_instruction_nonce(%s,%s,%s,%s,%s,%s)",
                (
                    "brain-gaming-pc",
                    rollback_nonce,
                    f"rollback-{instruction_id}",
                    "dev-laptop",
                    now + timedelta(minutes=5),
                    hashlib.sha256(f"rollback:{suffix}".encode("utf-8")).hexdigest(),
                ),
            )
            rollback_first_claim = bool(cur.fetchone()["consume_pet_instruction_nonce"])
        conn.rollback()
    rollback_claim_after_abort = guard.consume(
        "brain-gaming-pc",
        rollback_nonce,
        f"rollback-{instruction_id}",
        "dev-laptop",
        now + timedelta(minutes=5),
        now,
        hashlib.sha256(f"rollback:{suffix}".encode("utf-8")).hexdigest(),
    )

    with connect(local=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    has_function_privilege(
                        'aiops_replay_consumer',
                        'consume_pet_instruction_nonce(text,text,text,text,timestamptz,text)',
                        'execute'
                    ) as consumer_can_claim,
                    has_table_privilege(
                        'aiops_replay_consumer',
                        'pet_instruction_nonces',
                        'select,insert,update,delete'
                    ) as consumer_can_mutate_table,
                    has_function_privilege(
                        'aiops_replay_maintainer',
                        'prune_pet_instruction_nonces(interval,integer)',
                        'execute'
                    ) as maintainer_can_prune,
                    exists (
                        select 1
                        from aclexplode(p.proacl) acl
                        where acl.grantee = 0 and acl.privilege_type = 'EXECUTE'
                    ) as public_can_claim
                from pg_proc p
                where p.oid = 'consume_pet_instruction_nonce(text,text,text,text,timestamptz,text)'::regprocedure
                """
            )
            privileges = dict(cur.fetchone())

    append_only_enforced = False
    with connect(local=True) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from pet_instruction_nonces where signer_id = %s and nonce = %s",
                    ("brain-gaming-pc", nonce),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            append_only_enforced = True

    prune_nonce = f"prune-{nonce}"
    with connect(local=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set role aiops_replay_guard_owner")
            cur.execute(
                """
                insert into pet_instruction_nonces (
                    signer_id, nonce, instruction_id, target_machine_id,
                    expires_at, consumed_at, envelope_sha256, evidence_version
                ) values (%s, %s, %s, %s, %s, %s, null, 1)
                """,
                (
                    "legacy-audit-signer",
                    prune_nonce,
                    f"prune-{instruction_id}",
                    "dev-laptop",
                    now - timedelta(days=2),
                    now - timedelta(days=3),
                ),
            )
            cur.execute("reset role")
            cur.execute("set role aiops_replay_maintainer")
            cur.execute("select prune_pet_instruction_nonces(%s, %s) as pruned", (timedelta(days=1), 1000))
            pruned_rows = int(cur.fetchone()["pruned"])
            cur.execute("reset role")
        conn.commit()

    with connect(local=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) as count from pet_instruction_nonce_archive where signer_id = %s and nonce = %s",
                ("legacy-audit-signer", prune_nonce),
            )
            archived_rows = int(cur.fetchone()["count"])

    report = {
        "concurrent_attempts": len(concurrent_results),
        "atomic_winners": sum(concurrent_results),
        "replays_rejected": len(concurrent_results) - sum(concurrent_results),
        "separate_process_attempts": len(process_results),
        "separate_process_winners": sum(process_results),
        "expired_claim_accepted": expired,
        "same_nonce_distinct_signer_accepted": second_signer,
        "envelope_sha256": envelope_sha256,
        "restart_replay_accepted": restart_replay,
        "rollback_first_claim": rollback_first_claim,
        "rollback_claim_after_abort": rollback_claim_after_abort,
        "append_only_enforced": append_only_enforced,
        "consumer_can_claim": bool(privileges["consumer_can_claim"]),
        "consumer_can_mutate_table": bool(privileges["consumer_can_mutate_table"]),
        "maintainer_can_prune": bool(privileges["maintainer_can_prune"]),
        "public_can_claim": bool(privileges["public_can_claim"]),
        "pruned_rows": pruned_rows,
        "archived_rows": archived_rows,
    }
    report["passed"] = (
        report["atomic_winners"] == 1
        and report["replays_rejected"] == 39
        and report["separate_process_winners"] == 1
        and report["expired_claim_accepted"] is False
        and report["same_nonce_distinct_signer_accepted"] is True
        and report["restart_replay_accepted"] is False
        and report["rollback_first_claim"] is True
        and report["rollback_claim_after_abort"] is True
        and report["append_only_enforced"] is True
        and report["consumer_can_claim"] is True
        and report["consumer_can_mutate_table"] is False
        and report["maintainer_can_prune"] is True
        and report["public_can_claim"] is False
        and report["pruned_rows"] >= 1
        and report["archived_rows"] == 1
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
