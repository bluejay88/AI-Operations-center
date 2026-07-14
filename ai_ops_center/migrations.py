from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import ROOT, connect


MIGRATIONS_DIR = ROOT / "sql" / "migrations"

# Migration 002 was applied during the queue rollout with an extra idempotent
# active_task_id ALTER that is also present in migration 003. The repository
# version removes that duplicate statement. Accept only that exact historical
# checksum; all other applied-file changes remain fatal.
CHECKSUM_COMPATIBILITY: dict[str, set[str]] = {
    "002": {"829a0d27a5f2f03b9b27d54bab911a720b2aff555e659e5713480262431a69ad"},
    # Migration 018 was applied once while the parallel SSH lane was resolving
    # its version collision. The current file is the same runtime authority
    # contract with post-apply SQL hardening; accept only this recorded ledger
    # checksum and no other drift.
    "018": {"eea5aac7a3b21fb4e40e1ac199c35f4b13dcbd11c0e2673cc25f5a64cbda95f1"},
}


def _checksum_matches(version: str, applied_checksum: str, current_checksum: str) -> bool:
    return applied_checksum == current_checksum or applied_checksum in CHECKSUM_COMPATIBILITY.get(version, set())


def ensure_migration_table(local: bool = False) -> None:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists schema_migrations (
                    version text primary key,
                    name text not null,
                    checksum text not null,
                    applied_at timestamptz not null default now()
                )
                """
            )
        conn.commit()


def migration_status(local: bool = False) -> dict[str, Any]:
    ensure_migration_table(local=local)
    files = _migration_files()
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select version, name, checksum, applied_at from schema_migrations order by version")
            applied = {row["version"]: dict(row) for row in cur.fetchall()}

    pending = []
    applied_list = []
    for path in files:
        version, name = _parse_migration_name(path)
        checksum = _checksum(path)
        row = applied.get(version)
        item = {"version": version, "name": name, "path": str(path.relative_to(ROOT)), "checksum": checksum}
        if row:
            item["applied_at"] = row["applied_at"]
            item["checksum_matches"] = _checksum_matches(version, row["checksum"], checksum)
            applied_list.append(item)
        else:
            pending.append(item)
    return {
        "applied": applied_list,
        "pending": pending,
        "applied_count": len(applied_list),
        "pending_count": len(pending),
        "migration_dir": str(MIGRATIONS_DIR.relative_to(ROOT)),
    }


def apply_migrations(local: bool = False) -> dict[str, Any]:
    ensure_migration_table(local=local)
    applied_now = []
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_advisory_xact_lock(%s)", (2_026_071_302,))
            cur.execute("select version, checksum from schema_migrations")
            applied = {row["version"]: row["checksum"] for row in cur.fetchall()}
            for path in _migration_files():
                version, name = _parse_migration_name(path)
                checksum = _checksum(path)
                if version in applied:
                    if not _checksum_matches(version, applied[version], checksum):
                        raise RuntimeError(f"Migration {version} checksum changed after it was applied.")
                    continue
                sql = path.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    """
                    insert into schema_migrations (version, name, checksum)
                    values (%s, %s, %s)
                    on conflict (version) do nothing
                    """,
                    (version, name, checksum),
                )
                if cur.rowcount:
                    applied_now.append({"version": version, "name": name, "checksum": checksum})
                    applied[version] = checksum
        conn.commit()
    return {"applied": applied_now, "applied_count": len(applied_now), "status": migration_status(local=local)}


def _migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    files = sorted(path for path in MIGRATIONS_DIR.glob("*.sql") if path.is_file())
    versions: dict[str, Path] = {}
    for path in files:
        version, _ = _parse_migration_name(path)
        if version in versions:
            raise RuntimeError(
                f"Duplicate migration version {version}: {versions[version].name} and {path.name}. "
                "Migration versions must be unique."
            )
        versions[version] = path
    return files


def _parse_migration_name(path: Path) -> tuple[str, str]:
    stem = path.stem
    if "_" not in stem:
        return stem, stem
    version, name = stem.split("_", 1)
    return version, name.replace("_", " ")


def _checksum(path: Path) -> str:
    import hashlib

    # Git on Windows may rewrite SQL files from LF to CRLF in the working tree.
    # Migrations are immutable by content, not by platform-specific line endings.
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
