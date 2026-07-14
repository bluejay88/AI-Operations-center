from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .codex_pipeline import pipe_codex_request
from .db import connect
from .team_chat import post_team_chat_message


TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".js", ".ts", ".tsx", ".html", ".css", ".toml", ".yaml", ".yml"}
BUILD_FILES = {"package.json", "pyproject.toml", "requirements.txt", "Dockerfile", "docker-compose.yml"}
SECRET_NAME_HINTS = {"secret", "token", "apikey", "api_key", "key", "password", ".env"}
EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".next", "dist", "build"}
KNOWN_MACHINE_IDS = {"brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop", "security-monitor"}


def workspace_snapshot(limit: int = 80, local: bool = False) -> dict[str, Any]:
    imported = saved_project_scans(limit=limit, local=local)
    detected = detect_codex_workspaces(limit=limit)
    return {
        "detected": detected,
        "imported": imported,
        "usage": {
            "drop_or_paste_paths": "Use the dashboard intake panel or docker/scan-projects-to-brain.ps1.",
            "route_endpoint": "POST /project-intake/route",
            "import_endpoint": "POST /project-intake/import-scan",
        },
    }


def detect_codex_workspaces(limit: int = 80) -> list[dict[str, Any]]:
    roots: list[str] = []
    codex_state = Path.home() / ".codex" / ".codex-global-state.json"
    if codex_state.exists():
        try:
            state = json.loads(codex_state.read_text(encoding="utf-8"))
            roots.extend(state.get("electron-persisted-atom-state", {}).get("electron-saved-workspace-roots", []))
            roots.extend(state.get("electron-persisted-atom-state", {}).get("active-workspace-roots", []))
        except Exception:
            pass
    desktop = Path.home() / "OneDrive" / "Desktop"
    if desktop.exists():
        roots.extend(str(path) for path in desktop.iterdir() if path.is_dir())
    seen = set()
    projects = []
    for raw in roots:
        if not raw:
            continue
        path = Path(raw).expanduser()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        projects.append(_project_stub(path))
        if len(projects) >= limit:
            break
    return projects


def audit_project_paths(paths: list[str], source: str = "dashboard", local: bool = False) -> dict[str, Any]:
    reports = [_scan_path(Path(raw).expanduser()) for raw in paths if str(raw).strip()]
    result = {
        "source": source,
        "generated_at": _now(),
        "projects": reports,
        "summary": _summarize(reports),
    }
    save_project_scan(source=source, payload=result, local=local)
    post_team_chat_message(
        channel="project-intake",
        thread_key="portfolio-scan",
        actor_type="workflow",
        actor_id="project-intake",
        message_type="audit",
        priority=86,
        subject=f"Project intake scan imported {len(reports)} project(s)",
        body=_brief(result),
        metadata={"source": source, "project_count": len(reports), "summary": result["summary"]},
        local=local,
    )
    return result


def import_scan(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    source = str(payload.get("source") or "external-scanner")[:120]
    reported_machine_id = str(payload.get("machine_id") or "").strip()
    machine_id = reported_machine_id if reported_machine_id in KNOWN_MACHINE_IDS else None
    projects = payload.get("projects") or []
    if not isinstance(projects, list):
        projects = []
    normalized = {
        "source": source,
        "machine_id": machine_id,
        "reported_machine_id": reported_machine_id or None,
        "generated_at": payload.get("generated_at") or _now(),
        "projects": projects[:100],
        "summary": _summarize(projects),
    }
    scan_id = save_project_scan(source=source, payload=normalized, local=local)
    post_team_chat_message(
        channel="project-intake",
        thread_key="portfolio-scan",
        actor_type="machine" if reported_machine_id else "workflow",
        actor_id=reported_machine_id or source,
        machine_id=machine_id,
        message_type="audit",
        priority=88,
        subject=f"Imported project scan from {source}",
        body=_brief(normalized),
        metadata={
            "scan_id": scan_id,
            "source": source,
            "reported_machine_id": reported_machine_id or None,
            "summary": normalized["summary"],
        },
        local=local,
    )
    return {"scan_id": scan_id, "scan": normalized}


def route_project_intake(payload: dict[str, Any], local: bool = False) -> dict[str, Any]:
    projects = payload.get("projects") or []
    target_machines = payload.get("target_machines") or ["brain-gaming-pc", "dev-laptop", "research-laptop"]
    mode = str(payload.get("mode") or "audit-and-improve")
    created = []
    for project in projects[:25]:
        name = project.get("name") or project.get("path") or "Selected project"
        path = project.get("path") or "path not provided"
        body = _routing_body(project, mode)
        created.append(
            pipe_codex_request(
                {
                    "title": f"Portfolio intake: {name}",
                    "body": body,
                    "requester": payload.get("requester") or "project-intake",
                    "target_machines": target_machines,
                    "delivery_methods": payload.get("delivery_methods") or ["dashboard", "github"],
                    "priority": int(payload.get("priority") or 88),
                    "create_peer_requests": bool(payload.get("create_peer_requests", True)),
                    "project_id": _project_id(name),
                    "thread_key": f"project-intake-{_project_id(name)}",
                    "metadata": {"source": "project_intake", "project_path": path, "mode": mode, "scan": project},
                },
                local=local,
            )
        )
    return {"routed": len(created), "results": created}


def saved_project_scans(limit: int = 20, local: bool = False) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute("select * from project_intake_scans order by created_at desc, id desc limit %s", (limit,))
            rows = [dict(row) for row in cur.fetchall()]
    return rows


def save_project_scan(source: str, payload: dict[str, Any], local: bool = False) -> int:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute(
                """
                insert into project_intake_scans (source, project_count, summary, payload)
                values (%s, %s, %s::jsonb, %s::jsonb)
                returning id
                """,
                (source, len(payload.get("projects") or []), json.dumps(payload.get("summary") or {}), json.dumps(payload, default=str)),
            )
            scan_id = int(cur.fetchone()["id"])
        conn.commit()
    return scan_id


def _scan_path(path: Path) -> dict[str, Any]:
    report = _project_stub(path)
    if not path.exists() or not path.is_dir():
        report.update({"status": "not_found", "risks": ["Path was not reachable from this scanner."]})
        return report
    files = []
    suffixes: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    build_files = []
    docs = []
    recent = []
    max_files = 600
    for file_path in _iter_files(path, max_files=max_files):
        rel = str(file_path.relative_to(path))
        suffixes[file_path.suffix.lower() or "<none>"] += 1
        if file_path.name in BUILD_FILES:
            build_files.append(rel)
        if file_path.suffix.lower() in {".md", ".txt"}:
            docs.append(rel)
        if _looks_secretish(file_path):
            flags["secret_named_files"] += 1
        try:
            size = file_path.stat().st_size
        except OSError:
            size = 0
        if size > 5_000_000:
            flags["large_files"] += 1
        if file_path.suffix.lower() in TEXT_SUFFIXES and size < 400_000:
            text = _read_text(file_path)
            if re.search(r"\b(TODO|FIXME|SECURITY|placeholder|mock|blocked_external_secret)\b", text, re.I):
                flags["todo_or_security_markers"] += 1
        files.append(rel)
        recent.append((file_path.stat().st_mtime if file_path.exists() else 0, rel))
    recent.sort(reverse=True)
    report.update(
        {
            "status": "scanned",
            "file_count_sampled": len(files),
            "scan_limited": len(files) >= max_files,
            "suffix_counts": dict(suffixes.most_common(12)),
            "flag_counts": dict(flags),
            "build_files": build_files[:20],
            "docs": docs[:20],
            "recent_files": [rel for _, rel in recent[:12]],
            "recommended_tasks": _recommended_tasks(report["name"], build_files, flags),
        }
    )
    return report


def _project_stub(path: Path) -> dict[str, Any]:
    return {"name": path.name, "path": str(path), "kind": _kind(path), "status": "detected"}


def _kind(path: Path) -> str:
    if (path / "package.json").exists():
        return "javascript"
    if (path / "pyproject.toml").exists() or any(path.glob("*.py")):
        return "python"
    if any(path.glob("*.html")):
        return "web"
    return "folder"


def _iter_files(root: Path, max_files: int):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS and not name.startswith(".sandbox")]
        for name in filenames:
            if count >= max_files:
                return
            count += 1
            yield Path(dirpath) / name


def _looks_secretish(path: Path) -> bool:
    lowered = path.name.lower()
    return any(hint in lowered for hint in SECRET_NAME_HINTS)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:400_000]
    except Exception:
        return ""


def _recommended_tasks(name: str, build_files: list[str], flags: Counter[str]) -> list[dict[str, Any]]:
    tasks = [
        {"owner": "research-laptop", "agent": "research-lead", "title": f"{name}: product and market opportunity audit"},
        {"owner": "dev-laptop", "agent": "programmer", "title": f"{name}: build/test/security improvement plan"},
        {"owner": "brain-gaming-pc", "agent": "security-monitor", "title": f"{name}: security and approval gate review"},
    ]
    if build_files:
        tasks.append({"owner": "dev-laptop", "agent": "code-reviewer", "title": f"{name}: dependency, CI, and deploy readiness check"})
    if flags.get("secret_named_files"):
        tasks.append({"owner": "brain-gaming-pc", "agent": "security-monitor", "title": f"{name}: secret hygiene and redaction audit"})
    return tasks


def _summarize(projects: list[dict[str, Any]]) -> dict[str, Any]:
    flags: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    for project in projects:
        kinds[str(project.get("kind") or "unknown")] += 1
        flags.update(project.get("flag_counts") or {})
    return {"project_count": len(projects), "kinds": dict(kinds), "flags": dict(flags)}


def _brief(payload: dict[str, Any]) -> str:
    lines = [f"Project intake scan from {payload.get('source')} at {payload.get('generated_at')}."]
    for project in (payload.get("projects") or [])[:8]:
        lines.append(
            f"- {project.get('name')}: {project.get('kind')} / {project.get('status')} / "
            f"flags {project.get('flag_counts') or {}} / files {project.get('file_count_sampled', 'n/a')}"
        )
    return "\n".join(lines)


def _routing_body(project: dict[str, Any], mode: str) -> str:
    return (
        f"Project path: {project.get('path')}\n"
        f"Project kind: {project.get('kind')}\n"
        f"Mode: {mode}\n"
        f"Flags: {json.dumps(project.get('flag_counts') or {}, default=str)}\n"
        f"Build files: {', '.join(project.get('build_files') or []) or 'not detected'}\n"
        "Required output: audit summary, proposed improvements, security enhancements, data/modeling updates, "
        "test plan, risks, approval needs, and next implementation package. Do not edit external projects, deploy, "
        "spend money, contact customers, or expose secrets without Brain/Jayla approval."
    )


def _project_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "project"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(cur: Any) -> None:
    cur.execute(
        """
        create table if not exists project_intake_scans (
            id bigserial primary key,
            source text not null,
            project_count integer not null default 0,
            summary jsonb not null default '{}',
            payload jsonb not null default '{}',
            created_at timestamptz not null default now()
        )
        """
    )
    cur.execute("create index if not exists idx_project_intake_scans_time on project_intake_scans(created_at desc)")
    cur.execute("create index if not exists idx_project_intake_scans_source_time on project_intake_scans(source, created_at desc)")
