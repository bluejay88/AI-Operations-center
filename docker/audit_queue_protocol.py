from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import psycopg
from psycopg.rows import dict_row

from ai_ops_center.db import database_url


def main() -> None:
    evidence: dict[str, object] = {
        "observed_at": datetime.now(UTC).isoformat(),
        "expired_completion_rejected": False,
        "wrong_session_rejected": False,
        "valid_fenced_completion_accepted": False,
        "transaction_rolled_back": False,
    }
    token = str(uuid.uuid4())
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            insert into tasks (title, agent_id, category, description, priority, metadata, execution_machine_id)
            values ('QUEUE_PROTOCOL_AUDIT_ROLLBACK', 'chief-of-staff', 'audit',
                    'Transaction-rolled-back worker fencing audit.', 100, '{}', 'brain-gaming-pc')
            returning id
            """
        )
        task_id = int(cur.fetchone()["id"])
        evidence["temporary_task_id"] = task_id
        cur.execute(
            """
            update tasks
            set status='running', claim_token=%s, claimed_by_machine='brain-gaming-pc',
                lease_expires_at=now() - interval '1 second', started_at=now(), updated_at=now()
            where id=%s
            """,
            (token, task_id),
        )
        cur.execute("select set_config('aiops.claim_token', %s, true)", (token,))
        cur.execute("select set_config('aiops.machine_id', 'brain-gaming-pc', true)")

        cur.execute("savepoint expired_claim")
        try:
            cur.execute("update tasks set status='completed', result='invalid expired result' where id=%s", (task_id,))
        except psycopg.Error:
            evidence["expired_completion_rejected"] = True
            cur.execute("rollback to savepoint expired_claim")

        cur.execute("update tasks set lease_expires_at=now() + interval '5 minutes' where id=%s", (task_id,))
        cur.execute("select set_config('aiops.claim_token', 'wrong-token', true)")
        cur.execute("savepoint wrong_session")
        try:
            cur.execute("update tasks set status='completed', result='invalid wrong owner result' where id=%s", (task_id,))
        except psycopg.Error:
            evidence["wrong_session_rejected"] = True
            cur.execute("rollback to savepoint wrong_session")

        cur.execute("select set_config('aiops.claim_token', %s, true)", (token,))
        cur.execute(
            "update tasks set status='completed', result='valid fenced audit result' where id=%s returning id",
            (task_id,),
        )
        evidence["valid_fenced_completion_accepted"] = cur.fetchone() is not None
        conn.rollback()
        evidence["transaction_rolled_back"] = True

    if not all(
        evidence[key]
        for key in (
            "expired_completion_rejected",
            "wrong_session_rejected",
            "valid_fenced_completion_accepted",
            "transaction_rolled_back",
        )
    ):
        raise SystemExit(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
