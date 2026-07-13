from __future__ import annotations

import argparse
import json

from .approvals import approval_snapshot, create_approval_request, review_approval_request
from .benchmark import benchmark_report, run_benchmark
from .brain_bus import listener_snapshot, speaker_feed, submit_listener_event
from .db import init_db
from .factory import factory_snapshot, redistribute_business_queue
from .health import machine_status
from .integrations import integration_status
from .orchestrator import create_daily_priorities
from .ops2 import export_bundle, import_bundle, noc_snapshot, project_context, publish_device_telemetry, publish_workstation_update, seed_improvement_backlog, seed_laptop_work_batches, seed_operations_2, split_project
from .failover import evaluate_failover, evaluate_stale_workers
from .phoenix import laptop_instruction, phoenix_briefing, phoenix_snapshot, prompt_pack
from .readiness import readiness_report
from .registry import seed_registry
from .reports import generate_report
from .settings import get_settings
from .tasks import create_business_continuity, create_dev_kickoff
from .worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Operations Center control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("seed")
    subparsers.add_parser("daily-priorities")
    subparsers.add_parser("dev-kickoff")
    subparsers.add_parser("business-continuity")
    subparsers.add_parser("redistribute-business")
    subparsers.add_parser("status")
    subparsers.add_parser("readiness")
    subparsers.add_parser("factory")
    subparsers.add_parser("phoenix-status")
    subparsers.add_parser("phoenix-brief")
    subparsers.add_parser("agent-prompts")
    subparsers.add_parser("approvals")
    subparsers.add_parser("listener-events")
    subparsers.add_parser("integrations")
    subparsers.add_parser("ops2-seed")
    subparsers.add_parser("ops2-seed-improvements")
    laptop_work_parser = subparsers.add_parser("ops2-seed-laptop-work")
    laptop_work_parser.add_argument("--tasks-per-laptop", type=int, default=100)
    subparsers.add_parser("ops2-noc")
    subparsers.add_parser("failover-stale-workers")

    failover_parser = subparsers.add_parser("failover-evaluate")
    failover_parser.add_argument("--machine-id", required=True)
    failover_parser.add_argument("--battery-percent", type=float)
    failover_parser.add_argument("--state")
    failover_parser.add_argument("--trigger", default="cli")

    split_parser = subparsers.add_parser("ops2-split-project")
    split_parser.add_argument("--project-id", default="ai-operations-center-2")
    split_parser.add_argument("--template", default="website")

    context_parser = subparsers.add_parser("project-context")
    context_parser.add_argument("project_id")

    export_parser = subparsers.add_parser("export-bundle")
    export_parser.add_argument("--scope", choices=["all", "project", "ops"], default="all")
    export_parser.add_argument("--project-id", default="ai-operations-center-2")
    export_parser.add_argument("--output")

    import_parser = subparsers.add_parser("import-bundle")
    import_parser.add_argument("path")

    publish_parser = subparsers.add_parser("publish-update")
    publish_parser.add_argument("--machine-id", required=True)
    publish_parser.add_argument("--update-type", required=True)
    publish_parser.add_argument("--summary", required=True)
    publish_parser.add_argument("--agent-id")
    publish_parser.add_argument("--project-id")
    publish_parser.add_argument("--task-id", type=int)
    publish_parser.add_argument("--priority", type=int, default=50)
    publish_parser.add_argument("--outcome")

    telemetry_parser = subparsers.add_parser("publish-telemetry")
    telemetry_parser.add_argument("--machine-id", required=True)
    telemetry_parser.add_argument("--hostname")
    telemetry_parser.add_argument("--os")
    telemetry_parser.add_argument("--cpu")
    telemetry_parser.add_argument("--gpu")
    telemetry_parser.add_argument("--ram-mb", type=float)
    telemetry_parser.add_argument("--storage-free-mb", type=float)
    telemetry_parser.add_argument("--battery-percent", type=float)
    telemetry_parser.add_argument("--temperature-c", type=float)
    telemetry_parser.add_argument("--health-score", type=int)

    request_approval_parser = subparsers.add_parser("request-approval")
    request_approval_parser.add_argument("--title", required=True)
    request_approval_parser.add_argument("--type", default="change_request")
    request_approval_parser.add_argument("--machine", required=True)
    request_approval_parser.add_argument("--agent", required=True)
    request_approval_parser.add_argument("--risk", default="medium")
    request_approval_parser.add_argument("--summary", required=True)
    request_approval_parser.add_argument("--changes", required=True)

    review_parser = subparsers.add_parser("review-approval")
    review_parser.add_argument("id", type=int)
    review_parser.add_argument("decision", choices=["approved", "rejected", "needs_changes", "deployed"])
    review_parser.add_argument("--feedback", required=True)
    review_parser.add_argument("--actor", default="brain-gaming-pc")

    listener_parser = subparsers.add_parser("listen")
    listener_parser.add_argument("--source-id", required=True)
    listener_parser.add_argument("--event-type", required=True)
    listener_parser.add_argument("--subject", required=True)
    listener_parser.add_argument("--body", required=True)
    listener_parser.add_argument("--priority", type=int, default=50)
    listener_parser.add_argument("--source-type", default="machine")

    feed_parser = subparsers.add_parser("speaker-feed")
    feed_parser.add_argument("target_id")

    laptop_parser = subparsers.add_parser("laptop-instructions")
    laptop_parser.add_argument("machine", choices=["brain-gaming-pc", "dev-laptop", "research-laptop", "business-laptop"])

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--machine", default=get_settings().worker_machine_id)
    benchmark_parser.add_argument("--brain-host", default=get_settings().brain_host)

    subparsers.add_parser("benchmark-report")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("type", choices=["morning", "hourly", "daily", "weekly", "monthly", "quarterly"])

    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--machine", default=get_settings().worker_machine_id)
    worker_parser.add_argument("--once", action="store_true")
    worker_parser.add_argument("--sleep-seconds", type=int, default=get_settings().worker_sleep_seconds)

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
    elif args.command == "dev-kickoff":
        ids = create_dev_kickoff(local=args.local_db)
        print(f"Created Dev Laptop task IDs: {ids}")
    elif args.command == "business-continuity":
        ids = create_business_continuity(local=args.local_db)
        print(f"Created distributed business task IDs: {ids}")
    elif args.command == "redistribute-business":
        reassigned = redistribute_business_queue(local=args.local_db)
        print(json.dumps({"reassigned": reassigned}, indent=2, default=str))
    elif args.command == "status":
        print(machine_status(local=args.local_db))
    elif args.command == "readiness":
        print(readiness_report(local=args.local_db))
    elif args.command == "factory":
        print(json.dumps(factory_snapshot(local=args.local_db), indent=2, default=str))
    elif args.command == "phoenix-status":
        print(json.dumps(phoenix_snapshot(local=args.local_db), indent=2, default=str))
    elif args.command == "phoenix-brief":
        print(phoenix_briefing(local=args.local_db))
    elif args.command == "agent-prompts":
        print(prompt_pack())
    elif args.command == "laptop-instructions":
        print(laptop_instruction(args.machine))
    elif args.command == "approvals":
        print(json.dumps({"approvals": approval_snapshot(local=args.local_db)}, indent=2, default=str))
    elif args.command == "request-approval":
        request_id = create_approval_request(
            title=args.title,
            request_type=args.type,
            requester_machine_id=args.machine,
            requester_agent_id=args.agent,
            risk_level=args.risk,
            summary=args.summary,
            proposed_changes=args.changes,
            local=args.local_db,
        )
        print(f"Created approval request {request_id}")
    elif args.command == "review-approval":
        print(json.dumps(review_approval_request(args.id, args.decision, args.feedback, args.actor, local=args.local_db), indent=2, default=str))
    elif args.command == "listen":
        print(
            json.dumps(
                submit_listener_event(
                    source_type=args.source_type,
                    source_id=args.source_id,
                    event_type=args.event_type,
                    subject=args.subject,
                    body=args.body,
                    priority=args.priority,
                    local=args.local_db,
                ),
                indent=2,
                default=str,
            )
        )
    elif args.command == "listener-events":
        print(json.dumps({"events": listener_snapshot(local=args.local_db)}, indent=2, default=str))
    elif args.command == "speaker-feed":
        print(json.dumps(speaker_feed(args.target_id, local=args.local_db), indent=2, default=str))
    elif args.command == "integrations":
        print(json.dumps(integration_status(), indent=2, default=str))
    elif args.command == "ops2-seed":
        print(json.dumps(seed_operations_2(local=args.local_db), indent=2, default=str))
    elif args.command == "ops2-seed-improvements":
        print(json.dumps(seed_improvement_backlog(local=args.local_db), indent=2, default=str))
    elif args.command == "ops2-seed-laptop-work":
        print(json.dumps(seed_laptop_work_batches(tasks_per_laptop=args.tasks_per_laptop, local=args.local_db), indent=2, default=str))
    elif args.command == "ops2-noc":
        print(json.dumps(noc_snapshot(local=args.local_db), indent=2, default=str))
    elif args.command == "failover-evaluate":
        print(json.dumps(evaluate_failover(args.machine_id, args.battery_percent, args.state, args.trigger, local=args.local_db), indent=2, default=str))
    elif args.command == "failover-stale-workers":
        print(json.dumps(evaluate_stale_workers(local=args.local_db), indent=2, default=str))
    elif args.command == "ops2-split-project":
        print(json.dumps(split_project(args.project_id, args.template, local=args.local_db), indent=2, default=str))
    elif args.command == "project-context":
        print(json.dumps(project_context(args.project_id, local=args.local_db), indent=2, default=str))
    elif args.command == "export-bundle":
        bundle = export_bundle(scope=args.scope, project_id=args.project_id, local=args.local_db)
        output = json.dumps(bundle, indent=2, default=str)
        if args.output:
            from pathlib import Path

            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Exported bundle to {args.output}")
        else:
            print(output)
    elif args.command == "import-bundle":
        from pathlib import Path

        bundle = json.loads(Path(args.path).read_text(encoding="utf-8"))
        print(json.dumps(import_bundle(bundle, local=args.local_db), indent=2, default=str))
    elif args.command == "publish-update":
        print(
            json.dumps(
                publish_workstation_update(
                    {
                        "machine_id": args.machine_id,
                        "agent_id": args.agent_id,
                        "project_id": args.project_id,
                        "task_id": args.task_id,
                        "update_type": args.update_type,
                        "priority": args.priority,
                        "summary": args.summary,
                        "outcome": args.outcome,
                    },
                    local=args.local_db,
                ),
                indent=2,
                default=str,
            )
        )
    elif args.command == "publish-telemetry":
        print(
            json.dumps(
                publish_device_telemetry(
                    {
                        "machine_id": args.machine_id,
                        "hostname": args.hostname,
                        "operating_system": args.os,
                        "cpu": args.cpu,
                        "gpu": args.gpu,
                        "ram_mb": args.ram_mb,
                        "storage_free_mb": args.storage_free_mb,
                        "battery_percent": args.battery_percent,
                        "temperature_c": args.temperature_c,
                        "health_score": args.health_score,
                    },
                    local=args.local_db,
                ),
                indent=2,
                default=str,
            )
        )
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
