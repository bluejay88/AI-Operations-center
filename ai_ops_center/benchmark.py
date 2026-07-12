from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import urlopen

from .db import connect


@dataclass
class BenchmarkResult:
    machine_id: str
    hostname: str
    platform: str
    cpu_count: int
    cpu_score: float
    memory_total_mb: float
    memory_available_mb: float
    disk_free_mb: float
    disk_write_mb_s: float
    brain_latency_ms: float | None
    docker_available: bool
    python_version: str


def run_benchmark(machine_id: str, brain_host: str = "100.70.49.32", local: bool = False) -> BenchmarkResult:
    result = BenchmarkResult(
        machine_id=machine_id,
        hostname=socket.gethostname(),
        platform=platform.platform(),
        cpu_count=os.cpu_count() or 1,
        cpu_score=_cpu_score(),
        memory_total_mb=_memory_mb()[0],
        memory_available_mb=_memory_mb()[1],
        disk_free_mb=_disk_free_mb(),
        disk_write_mb_s=_disk_write_mb_s(),
        brain_latency_ms=_brain_latency_ms(brain_host),
        docker_available=_docker_available(),
        python_version=sys.version.split()[0],
    )
    save_benchmark(result, local=local)
    return result


def save_benchmark(result: BenchmarkResult, local: bool = False) -> None:
    raw = asdict(result)
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into machine_benchmarks (
                    machine_id, hostname, platform, cpu_count, cpu_score,
                    memory_total_mb, memory_available_mb, disk_free_mb,
                    disk_write_mb_s, brain_latency_ms, docker_available,
                    python_version, raw
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    result.machine_id,
                    result.hostname,
                    result.platform,
                    result.cpu_count,
                    result.cpu_score,
                    result.memory_total_mb,
                    result.memory_available_mb,
                    result.disk_free_mb,
                    result.disk_write_mb_s,
                    result.brain_latency_ms,
                    result.docker_available,
                    result.python_version,
                    json.dumps(raw),
                ),
            )
        conn.commit()


def benchmark_report(local: bool = False) -> str:
    with connect(local=local) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct on (machine_id)
                    machine_id, hostname, cpu_count, cpu_score,
                    memory_total_mb, memory_available_mb, disk_free_mb,
                    disk_write_mb_s, brain_latency_ms, docker_available,
                    created_at
                from machine_benchmarks
                order by machine_id, created_at desc
                """
            )
            rows = cur.fetchall()

    lines = ["# Machine Benchmark Report", ""]
    if not rows:
        return "\n".join(lines + ["No benchmarks recorded yet."])

    ranked = sorted(rows, key=lambda row: _role_score(row), reverse=True)
    for row in ranked:
        lines.append(
            "- {machine} ({host}): score {score:.0f}, cpu {cpu}, mem {mem:.0f}MB free, "
            "disk {disk:.0f}MB free, write {write:.1f}MB/s, latency {latency}, docker {docker}".format(
                machine=row["machine_id"],
                host=row["hostname"] or "unknown",
                score=_role_score(row),
                cpu=row["cpu_count"] or 0,
                mem=float(row["memory_available_mb"] or 0),
                disk=float(row["disk_free_mb"] or 0),
                write=float(row["disk_write_mb_s"] or 0),
                latency="n/a" if row["brain_latency_ms"] is None else f"{float(row['brain_latency_ms']):.1f}ms",
                docker="yes" if row["docker_available"] else "no",
            )
        )

    lines.extend(["", "## Suggested Roles"])
    suggestions = suggest_roles(ranked)
    lines.extend(f"- {role}: {machine}" for role, machine in suggestions.items())
    return "\n".join(lines)


def suggest_roles(rows: list[dict]) -> dict[str, str]:
    if not rows:
        return {}

    available = list(rows)
    suggestions: dict[str, str] = {}

    def take_best(role: str, key) -> None:
        if not available:
            return
        best = max(available, key=key)
        suggestions[role] = best["machine_id"]
        available.remove(best)

    take_best("development", lambda row: float(row["cpu_score"] or 0) + float(row["memory_available_mb"] or 0) / 256)
    take_best("research", lambda row: (1000 - float(row["brain_latency_ms"] or 1000)) + float(row["disk_free_mb"] or 0) / 1024)
    take_best("business", lambda row: float(row["memory_available_mb"] or 0) + (500 if row["docker_available"] else 0))
    return suggestions


def _role_score(row: dict) -> float:
    latency_penalty = float(row["brain_latency_ms"] or 1000)
    return (
        float(row["cpu_score"] or 0) * 10
        + float(row["memory_available_mb"] or 0) / 64
        + float(row["disk_write_mb_s"] or 0)
        + (500 if row["docker_available"] else 0)
        - latency_penalty
    )


def _cpu_score() -> float:
    start = time.perf_counter()
    total = 0
    for number in range(1, 2_500_00):
        total += (number * number) % 97
    elapsed = max(time.perf_counter() - start, 0.001)
    return round(total / elapsed / 1_000_000, 2)


def _memory_mb() -> tuple[float, float]:
    try:
        import psutil  # type: ignore

        memory = psutil.virtual_memory()
        return round(memory.total / 1024 / 1024, 2), round(memory.available / 1024 / 1024, 2)
    except Exception:
        return 0.0, 0.0


def _disk_free_mb() -> float:
    usage = shutil.disk_usage(Path.cwd())
    return round(usage.free / 1024 / 1024, 2)


def _disk_write_mb_s() -> float:
    data = b"0" * (8 * 1024 * 1024)
    with tempfile.NamedTemporaryFile(delete=True) as handle:
        start = time.perf_counter()
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        elapsed = max(time.perf_counter() - start, 0.001)
    return round(8 / elapsed, 2)


def _brain_latency_ms(brain_host: str) -> float | None:
    start = time.perf_counter()
    try:
        with urlopen(f"http://{brain_host}:8088/health", timeout=10) as response:
            response.read()
        return round((time.perf_counter() - start) * 1000, 2)
    except Exception:
        return None


def _docker_available() -> bool:
    try:
        completed = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False
