from __future__ import annotations

import argparse

from .benchmark import benchmark_report, run_benchmark
from .db import init_db
from .health import machine_status
from .orchestrator import create_daily_priorities
from .registry import seed_registry
from .reports import generate_report
from .settings import get_settings
from .worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Operations Center control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("seed")
    subparsers.add_parser("daily-priorities")
    subparsers.add_parser("status")

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--machine", default=get_settings().worker_machine_id)
    benchmark_parser.add_argument("--brain-host", default=get_settings().brain_host)

    subparsers.add_parser("benchmark-report")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("type", choices=["morning", "hourly", "daily", "weekly", "monthly", "quarterly"])

    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--machine", default=get_settings().worker_machine_id)
    worker_parser.add_argument("--once", action="store_true")
    worker_parser.add_argument("--sleep-seconds", type=int, default=15)

    parser.add_argument("--local-db", action="store_true", help="Use LOCAL_DATABASE_URL instead of DATABASE_URL")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db(local=args.local_db)
        print("Database initialized.")
    elif args.command == "seed":
        seed_registry(local=args.local_db)
        print("Registry seeded.")
    elif args.command == "daily-priorities":
        ids = create_daily_priorities(local=args.local_db)
        print(f"Created task IDs: {ids}")
    elif args.command == "status":
        print(machine_status(local=args.local_db))
    elif args.command == "benchmark":
        result = run_benchmark(args.machine, brain_host=args.brain_host, local=args.local_db)
        print(result)
    elif args.command == "benchmark-report":
        print(benchmark_report(local=args.local_db))
    elif args.command == "report":
        print(generate_report(args.type, local=args.local_db))
    elif args.command == "worker":
        run_worker(args.machine, once=args.once, sleep_seconds=args.sleep_seconds, local=args.local_db)


if __name__ == "__main__":
    main()
