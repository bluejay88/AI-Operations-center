"""Non-secret production authentication and authorization smoke test."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8088"


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        name, value = raw.split("=", 1)
        values[name] = value.strip().strip("'").strip('"')
    return values


def _request(path: str, *, token: str | None = None, machine_id: str | None = None, body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if machine_id:
        headers["X-AI-Ops-Device-Id"] = machine_id
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, headers=headers, data=data, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> None:
    env = _env()
    device_tokens = json.loads(env["DEVICE_API_TOKENS_JSON"])
    checks: list[tuple[str, bool]] = []

    status, _ = _request("/health")
    checks.append(("public health", status == 200))
    status, _ = _request("/approvals")
    checks.append(("anonymous protected-route denial", status == 401))
    status, _ = _request("/approvals", token=env["API_CONTROL_TOKEN"])
    checks.append(("Brain control authorization", status == 200))
    status, broker = _request("/ssh-broker/status", token=env["API_CONTROL_TOKEN"])
    checks.append(("SSH broker authorization", status == 200 and isinstance(broker, dict)))

    password = (ROOT / "state" / "dashboard-bootstrap-password.txt").read_text(encoding="ascii").strip()
    status, first = _request("/dashboard/login", body={"password": password})
    status2, second = _request("/dashboard/login", body={"password": password})
    unique = status == status2 == 200 and first.get("token") and first.get("token") != second.get("token")
    checks.append(("expiring unique dashboard sessions", bool(unique)))
    if first.get("token"):
        status, _ = _request("/approvals", token=first["token"])
        checks.append(("dashboard operator authorization", status == 200))

    dev_token = device_tokens["dev-laptop"]
    status, readiness = _request("/readiness.json", token=dev_token, machine_id="dev-laptop")
    checks.append(("DEV scoped read authorization", status == 200))
    dev = next((machine for machine in readiness.get("machines", []) if machine.get("id") == "dev-laptop"), {})
    status, _ = _request("/speaker/feed/dev-laptop", token=dev_token, machine_id="dev-laptop")
    checks.append(("DEV identity-bound speaker feed", status == 200))
    status, _ = _request("/speaker/feed/research-laptop", token=dev_token, machine_id="dev-laptop")
    checks.append(("DEV cross-device denial", status == 403))

    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    print(f"DEV readiness state={dev.get('state', 'unknown')} last_seen={dev.get('last_seen', 'unknown')}")
    if failed:
        raise SystemExit(f"Secure deployment verification failed ({len(failed)} checks).")
    print(f"Secure deployment verification passed ({len(checks)} checks); no credentials displayed.")


if __name__ == "__main__":
    main()
