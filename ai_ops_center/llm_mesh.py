from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from .integrations import dispatch_to_provider, integration_status
from .settings import get_settings


ROOT = Path(__file__).resolve().parent.parent
MESH_CONFIG = ROOT / "config" / "llm_mesh.yaml"

MODE_KEYWORDS: dict[str, set[str]] = {
    "coding": {"code", "python", "react", "api", "debug", "unit test", "refactor", "function", "dockerfile"},
    "debugging": {"error", "traceback", "bug", "failing", "fix", "exception", "broken"},
    "research": {"research", "grant", "market", "news", "zillow", "paper", "competitor", "trend"},
    "qa": {"question", "answer", "explain", "what is", "how do", "compare"},
    "generation": {"generate", "draft", "write", "create", "proposal", "campaign", "blog", "website"},
    "edge": {"edge", "offline", "local", "low power", "laptop"},
}

SENSITIVE_TERMS = {
    "secret",
    "password",
    "api key",
    "token",
    "credential",
    "bank",
    "ssn",
    "legal filing",
    "deploy public",
}


@dataclass(frozen=True)
class RouteCandidate:
    profile_id: str
    provider: str
    model: str
    score: float
    reasons: list[str]
    local_only: bool
    max_tokens: int


def mesh_config() -> dict[str, Any]:
    return yaml.safe_load(MESH_CONFIG.read_text(encoding="utf-8"))


def mesh_status() -> dict[str, Any]:
    config = mesh_config()
    providers = {item["id"]: item for item in integration_status()["providers"]}
    profiles = []
    for profile_id, profile in config["profiles"].items():
        provider = str(profile["provider"])
        configured = provider == "ollama" or bool(providers.get(provider, {}).get("configured"))
        profiles.append(
            {
                "id": profile_id,
                "provider": provider,
                "model": profile["model"],
                "roles": profile.get("roles", []),
                "strengths": profile.get("strengths", []),
                "configured": configured,
                "local_only": bool(profile.get("local_only")),
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "profiles": profiles,
        "policies": config.get("policies", {}),
        "guardrails": config.get("guardrails", {}),
    }


def classify_prompt(prompt: str, requested_mode: str | None = None) -> dict[str, Any]:
    text = prompt.lower()
    scores: dict[str, int] = {}
    for mode, keywords in MODE_KEYWORDS.items():
        scores[mode] = sum(1 for keyword in keywords if keyword in text)
    if requested_mode:
        scores[requested_mode] = scores.get(requested_mode, 0) + 4
    mode = max(scores, key=lambda key: scores[key]) if any(scores.values()) else "chat"
    sensitive = any(term in text for term in SENSITIVE_TERMS)
    complexity = min(100, 20 + len(prompt) // 40 + (20 if mode in {"coding", "debugging", "research"} else 0))
    return {"mode": mode, "scores": scores, "sensitive": sensitive, "complexity": complexity}


def route_prompt(
    prompt: str,
    mode: str | None = None,
    local_only: bool = False,
    prefer_speed: bool = False,
    edge_device: bool = False,
) -> dict[str, Any]:
    config = mesh_config()
    classification = classify_prompt(prompt, mode)
    selected_mode = "offline" if local_only else ("edge" if edge_device else classification["mode"])
    policy = config["policies"].get(selected_mode) or config["policies"].get("chat", {})
    ordered = list(policy.get("fallback_order", []))
    if classification["sensitive"] and not local_only:
        local_first = [profile_id for profile_id in ordered if config["profiles"][profile_id].get("local_only")]
        remote_rest = [profile_id for profile_id in ordered if profile_id not in local_first]
        ordered = local_first + remote_rest

    candidates = [
        _score_candidate(
            profile_id,
            config["profiles"][profile_id],
            classification,
            local_only,
            prefer_speed,
            edge_device,
            bool(policy.get("prefer_local")),
        )
        for profile_id in ordered
        if profile_id in config["profiles"]
    ]
    candidates = [candidate for candidate in candidates if candidate.score > -1_000]
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return {
        "selected_mode": selected_mode,
        "classification": classification,
        "candidates": [_candidate_dict(candidate) for candidate in candidates],
        "selected": _candidate_dict(candidates[0]) if candidates else None,
        "fallback_order": [_candidate_dict(candidate) for candidate in candidates],
    }


async def run_llm_request(
    prompt: str,
    mode: str | None = None,
    local_only: bool = False,
    prefer_speed: bool = False,
    edge_device: bool = False,
    max_tokens: int | None = None,
    temperature: float = 0.2,
    local: bool = False,
) -> dict[str, Any]:
    plan = route_prompt(prompt, mode=mode, local_only=local_only, prefer_speed=prefer_speed, edge_device=edge_device)
    failures = []
    for candidate_data in plan["fallback_order"]:
        provider = candidate_data["provider"]
        model = candidate_data["model"]
        options = {"model": model, "max_tokens": max_tokens or candidate_data["max_tokens"], "temperature": temperature}
        try:
            if provider == "ollama":
                result = await _dispatch_ollama(prompt, plan["selected_mode"], options)
                if result.get("status") == "completed":
                    return {"status": "completed", "route": candidate_data, "plan": plan, "result": result}
                failures.append({"route": candidate_data, "error": result.get("error") or result.get("status")})
            else:
                response = await dispatch_to_provider(provider, f"llm_mesh:{plan['selected_mode']}", prompt, options=options, local=local)
                result = response.get("result", {})
                if result.get("status") == "completed" and str(result.get("text") or "").strip():
                    return {"status": "completed", "route": candidate_data, "plan": plan, "result": result}
                failures.append({"route": candidate_data, "error": result.get("error") or result.get("status")})
        except Exception as exc:
            failures.append({"route": candidate_data, "error": _safe_text(str(exc))})
    return {"status": "failed", "plan": plan, "failures": failures}


async def _dispatch_ollama(prompt: str, purpose: str, options: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    model = options["model"]
    started = datetime.now(UTC)
    system = (
        f"AI Operations Center local model task: {purpose}. "
        "Be direct, accurate, security-aware, and do not claim actions that were not performed."
    )
    try:
        async with httpx.AsyncClient(timeout=float(options.get("timeout_seconds", 75))) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {
                        "temperature": float(options.get("temperature", 0.2)),
                        "num_predict": int(options.get("max_tokens", 700)),
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
        text = ((payload.get("message") or {}).get("content") or payload.get("response") or "").strip()
        return {
            "status": "completed",
            "provider": "ollama",
            "model": model,
            "text": text,
            "latency_ms": round((datetime.now(UTC) - started).total_seconds() * 1000, 2),
            "raw_summary": {"done": payload.get("done"), "eval_count": payload.get("eval_count")},
        }
    except Exception as exc:
        return {"status": "failed", "provider": "ollama", "model": model, "error": _safe_text(str(exc))}


def _score_candidate(
    profile_id: str,
    profile: dict[str, Any],
    classification: dict[str, Any],
    local_only: bool,
    prefer_speed: bool,
    edge_device: bool,
    prefer_local: bool,
) -> RouteCandidate:
    if local_only and not profile.get("local_only"):
        return RouteCandidate(profile_id, profile["provider"], profile["model"], -10_000, ["blocked_non_local"], bool(profile.get("local_only")), int(profile.get("max_tokens", 700)))
    roles = set(profile.get("roles", []))
    strengths = set(profile.get("strengths", []))
    mode = classification["mode"]
    score = 0.0
    reasons = []
    if mode in roles:
        score += 35
        reasons.append(f"role_match:{mode}")
    if classification["sensitive"] and profile.get("local_only"):
        score += 22
        reasons.append("sensitive_local_preference")
    if prefer_local and profile.get("local_only"):
        score += 18
        reasons.append("policy_local_preference")
    if prefer_speed:
        score += float(profile.get("latency_weight", 50)) * 0.35
        reasons.append("speed_weighted")
    if edge_device and ("edge" in strengths or profile.get("local_only")):
        score += 20
        reasons.append("edge_ready")
    score += float(profile.get("quality_weight", 50)) * 0.25
    score += float(profile.get("reliability_weight", 50)) * 0.25
    score += float(profile.get("cost_weight", 50)) * 0.10
    if profile.get("local_only"):
        score += 5
    return RouteCandidate(
        profile_id=profile_id,
        provider=profile["provider"],
        model=profile["model"],
        score=round(score, 2),
        reasons=reasons or ["policy_fallback"],
        local_only=bool(profile.get("local_only")),
        max_tokens=int(profile.get("max_tokens", 700)),
    )


def _candidate_dict(candidate: RouteCandidate) -> dict[str, Any]:
    return {
        "profile_id": candidate.profile_id,
        "provider": candidate.provider,
        "model": candidate.model,
        "score": candidate.score,
        "reasons": candidate.reasons,
        "local_only": candidate.local_only,
        "max_tokens": candidate.max_tokens,
    }


def _safe_text(text: str) -> str:
    for pattern in mesh_config().get("guardrails", {}).get("redact_patterns", []):
        text = re.sub(re.escape(pattern) + r"[A-Za-z0-9_\-]*", pattern + "[redacted]", text, flags=re.IGNORECASE)
    return text[:800]
