"""Run live security audits and print bounded, non-secret summaries."""
from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_control_token() -> None:
    for raw in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if raw.startswith("API_CONTROL_TOKEN="):
            os.environ["API_CONTROL_TOKEN"] = raw.split("=", 1)[1].strip().strip("'").strip('"')


def _print(name: str, result: dict) -> None:
    print(f"{name} passed={result['passed']}/{result['total']}", flush=True)
    for check in result["checks"]:
        if not check["ok"]:
            detail = str(check.get("detail", "")).replace("\n", " ")[:240]
            print(f"FAIL {check['name']}: {detail}", flush=True)


def main() -> None:
    _load_control_token()
    from ai_ops_center.audit50 import run_audit
    from ai_ops_center.security_guardian import security_guardian_audit

    _print("SecurityGuardian", security_guardian_audit(local=True))
    _print("Audit50", run_audit(base_url="http://127.0.0.1:8088"))


if __name__ == "__main__":
    main()
