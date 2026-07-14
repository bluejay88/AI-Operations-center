from __future__ import annotations

import logging
import asyncio
import json
import platform
import socket
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import UTC, datetime

from .brain_bus import acknowledge_speaker_message, speaker_feed, submit_listener_event
from .collaboration import respond_to_peer_request
from .integrations import integration_status
from .llm_mesh import run_llm_request
from .migrations import apply_migrations
from .orchestrator import claim_next_task, complete_task, fail_task, record_heartbeat, renew_task_lease
from .pet_instruction_protocol import InstructionDecision, PostgresReplayGuard, verify_instruction
from .queue_manager import steward_queue
from .settings import get_settings

logger = logging.getLogger(__name__)

SIGNED_INSTRUCTION_MESSAGE_TYPES = {"brain_instruction", "signed_instruction"}


def run_worker(machine_id: str, once: bool = False, sleep_seconds: int = 15, work_seconds: int = 4, local: bool = False) -> None:
    if work_seconds < 0:
        raise ValueError("work_seconds cannot be negative")
    apply_migrations(local=local)
    last_steward_at = 0.0
    while True:
        record_heartbeat(machine_id, local=local)
        _consume_machine_messages(machine_id, local=local)
        if time.monotonic() - last_steward_at >= 5:
            try:
                steward_queue(local=local)
            except Exception:
                logger.exception("Queue steward failed; worker will continue claiming eligible tasks")
            last_steward_at = time.monotonic()
        task = claim_next_task(machine_id, local=local)
        if task:
            record_heartbeat(machine_id, active_task_id=task["id"], local=local)
            try:
                result = _execute_with_lease_heartbeats(machine_id, task, local=local)
                completed = complete_task(task["id"], result, task["claim_token"], machine_id, local=local)
                if completed:
                    _report_task_completion(machine_id, task, result, local=local)
                    _respond_to_linked_peer_request(machine_id, task, result, local=local)
            except Exception as exc:
                fail_task(task["id"], str(exc), task["claim_token"], machine_id, local=local)
                if once:
                    raise
        if once:
            return
        if task:
            continue
        time.sleep(sleep_seconds)


def _consume_machine_messages(machine_id: str, local: bool = False) -> int:
    """Acknowledge direct machine messages and emit auditable proof of receipt."""
    try:
        messages = speaker_feed(machine_id, local=local).get("messages", [])
    except Exception:
        logger.exception("Unable to read speaker feed for %s", machine_id)
        return 0

    acknowledged = 0
    for message in messages:
        if message.get("target_id") != machine_id or message.get("status") == "acknowledged":
            continue
        try:
            decision = _verify_brain_instruction_message(message, machine_id, local=local)
            if decision is not None and not decision.accepted:
                _report_instruction_rejection(message, machine_id, decision, local=local)
                continue
            submit_listener_event(
                source_type="machine",
                source_id=machine_id,
                event_type="speaker_message_received",
                subject=f"Received: {message['subject']}",
                body=f"{machine_id} received speaker message {message['id']} and is listening.",
                priority=int(message.get("priority") or 50),
                metadata={"speaker_message_id": message["id"], "machine_id": machine_id},
                local=local,
            )
            acknowledge_speaker_message(message["id"], actor=machine_id, local=local)
            acknowledged += 1
        except Exception:
            logger.exception("Unable to acknowledge speaker message %s", message.get("id"))
    return acknowledged


def _verify_brain_instruction_message(message: dict, machine_id: str, local: bool = False) -> InstructionDecision | None:
    metadata = dict(message.get("metadata") or {})
    envelope = metadata.get("instruction_envelope")
    requires_signature = message.get("message_type") in SIGNED_INSTRUCTION_MESSAGE_TYPES or envelope is not None
    if not requires_signature:
        return None
    if not isinstance(envelope, dict):
        return InstructionDecision(False, "malformed_instruction", "PET-02-04", target_machine_id=machine_id)

    configured_secret = get_settings().brain_instruction_secret.encode("utf-8")
    signer_id = str(envelope.get("signer_id") or "")
    return verify_instruction(
        envelope,
        expected_machine_id=machine_id,
        secret_for_signer=lambda requested_signer: (
            configured_secret if requested_signer == "brain-gaming-pc" and requested_signer == signer_id else None
        ),
        replay_guard=PostgresReplayGuard(local=local),
    )


def _report_instruction_rejection(
    message: dict,
    machine_id: str,
    decision: InstructionDecision,
    local: bool = False,
) -> None:
    submit_listener_event(
        source_type="machine",
        source_id=machine_id,
        event_type="speaker_message_rejected",
        subject=f"Rejected Brain instruction: {message.get('subject') or message.get('id')}",
        body=f"Instruction was not acknowledged or executed: {decision.code}.",
        priority=max(90, int(message.get("priority") or 50)),
        metadata={
            "speaker_message_id": message.get("id"),
            "machine_id": machine_id,
            "instruction_decision": decision.as_dict(),
        },
        local=local,
    )


def _report_task_completion(machine_id: str, task: dict, result: str, local: bool = False) -> None:
    try:
        submit_listener_event(
            source_type="machine",
            source_id=machine_id,
            event_type="task_completed",
            subject=f"Task completed: {task['title']}",
            body=result,
            priority=int(task.get("priority") or 50),
            metadata={
                "task_id": task["id"],
                "agent_id": task["agent_id"],
                "machine_id": machine_id,
                "claim_token": task["claim_token"],
            },
            local=local,
        )
    except Exception:
        logger.exception("Task %s completed but its listener pulse failed", task.get("id"))


def _execute_with_lease_heartbeats(machine_id: str, task: dict, local: bool = False) -> str:
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="aiops-task") as pool:
        future = pool.submit(_execute_task, machine_id, task, local)
        while True:
            try:
                return future.result(timeout=30)
            except FutureTimeoutError:
                if not renew_task_lease(task["id"], task["claim_token"], machine_id, local=local):
                    raise RuntimeError("Task lease ownership was lost while executing")
                record_heartbeat(machine_id, active_task_id=task["id"], local=local)


def _execute_task(machine_id: str, task: dict, local: bool = False) -> str:
    metadata = dict(task.get("metadata") or {})
    executor = str(metadata.get("executor") or "model").strip().lower()
    if executor == "connectivity_probe":
        return json.dumps(
            {
                "status": "completed",
                "executor": executor,
                "machine_id": machine_id,
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "python": platform.python_version(),
                "observed_at": datetime.now(UTC).isoformat(),
                "task_id": task["id"],
            },
            sort_keys=True,
        )
    if executor != "model":
        raise RuntimeError(f"No approved worker executor is registered for {executor!r}")
    return asyncio.run(_execute_model_task(machine_id, task, metadata, local=local))


async def _execute_model_task(machine_id: str, task: dict, metadata: dict, local: bool = False) -> str:
    requested = metadata.get("providers")
    configured = [item["id"] for item in integration_status()["providers"] if item.get("configured") and item["id"] in {"openai", "groq", "claude", "gemini"}]
    providers = [str(item) for item in requested] if isinstance(requested, list) else configured
    local_only = bool(metadata.get("local_only") or metadata.get("edge_device"))
    if not providers and not local_only:
        raise RuntimeError("No model provider is configured; task was not falsely completed")
    prompt = (
        f"Machine: {machine_id}\nAgent: {task['agent_id']}\nCategory: {task['category']}\n"
        f"Task: {task['title']}\n\n{task.get('description') or ''}\n\n"
        "Return a concrete work product, evidence/assumptions, blockers, confidence, and next action. "
        "Do not claim external actions or files unless actually performed."
    )
    response = await run_llm_request(
        prompt,
        mode=str(metadata.get("mode") or task["category"]),
        local_only=local_only,
        prefer_speed=bool(metadata.get("prefer_speed")),
        edge_device=bool(metadata.get("edge_device")),
        max_tokens=int(metadata.get("max_tokens") or 1200),
        temperature=float(metadata.get("temperature") or 0.2),
        local=local,
    )
    if response.get("status") != "completed":
        failures = response.get("failures") or []
        raise RuntimeError("All LLM mesh routes failed: " + json.dumps(failures, default=str)[:1500])
    result = response.get("result") or {}
    return json.dumps(
        {
            "status": "completed",
            "executor": "llm_mesh",
            "route": response.get("route"),
            "latency_ms": result.get("latency_ms"),
            "work_product": result.get("text"),
        },
        default=str,
    )


def _respond_to_linked_peer_request(machine_id: str, task: dict, result: str, local: bool = False) -> None:
    metadata = dict(task.get("metadata") or {})
    request_id = metadata.get("peer_request_id")
    if not request_id:
        return
    try:
        respond_to_peer_request(
            request_id=int(request_id),
            responder_machine_id=machine_id,
            response_body=result,
            status="fulfilled",
            quality_score=100,
            metadata={"task_id": task["id"], "claim_token": task["claim_token"]},
            local=local,
        )
    except Exception:
        logger.exception("Task %s completed but peer request %s response failed", task.get("id"), request_id)
