import time

import pytest

from ai_ops_center.auth import (
    authenticate_request,
    enforce_device_identity,
    hash_dashboard_password,
    issue_dashboard_token,
    require_fleet_controller,
    require_human_operator,
    validate_security_settings,
    verify_dashboard_password,
    verify_dashboard_token,
)
from ai_ops_center.settings import Settings


class Request:
    def __init__(self, settings, headers=None, principal=None):
        self.headers = headers or {}
        self.state = type("State", (), {})()
        if principal is not None:
            self.state.principal = principal
        self.app = type("App", (), {"state": type("AppState", (), {"settings": settings})()})()


def settings(**overrides):
    values = {
        "app_env": "local",
        "dashboard_session_secret": "s" * 40,
        "api_control_token": "c" * 40,
        "dashboard_password_hash": hash_dashboard_password("correct horse battery"),
        "device_api_tokens_json": '{"dev-laptop":"d%s"}' % ("e" * 39),
    }
    values.update(overrides)
    return Settings(**values)


def test_dashboard_password_hash_and_session_token_round_trip():
    cfg = settings()
    assert verify_dashboard_password("correct horse battery", cfg.dashboard_password_hash)
    assert not verify_dashboard_password("wrong horse battery", cfg.dashboard_password_hash)
    token, expires_at = issue_dashboard_token(cfg, now=100)
    principal = verify_dashboard_token(token, cfg, now=101)
    assert principal is not None
    assert principal.is_human_operator
    assert expires_at > int(time.time()) or expires_at == 3700
    assert verify_dashboard_token(token, cfg, now=expires_at + 1) is None


def test_production_auth_fails_closed_without_required_secrets():
    with pytest.raises(RuntimeError, match="API_CONTROL_TOKEN"):
        validate_security_settings(Settings(app_env="production"))


def test_bearer_auth_distinguishes_brain_operator_and_device():
    cfg = settings(api_auth_required=True)
    brain = authenticate_request(Request(cfg, {"authorization": f"Bearer {cfg.api_control_token}"}), cfg)
    assert brain is not None and brain.can_control_fleet
    token, _ = issue_dashboard_token(cfg)
    operator = authenticate_request(Request(cfg, {"authorization": f"Bearer {token}"}), cfg)
    assert operator is not None and operator.is_human_operator
    device_token = cfg.device_api_tokens()["dev-laptop"]
    device = authenticate_request(
        Request(cfg, {"authorization": f"Bearer {device_token}", "x-ai-ops-device-id": "dev-laptop"}),
        cfg,
    )
    assert device is not None and device.machine_id == "dev-laptop"


def test_device_identity_cannot_write_for_another_machine():
    cfg = settings(api_auth_required=True)
    device_token = cfg.device_api_tokens()["dev-laptop"]
    principal = authenticate_request(
        Request(cfg, {"authorization": f"Bearer {device_token}", "x-ai-ops-device-id": "dev-laptop"}),
        cfg,
    )
    with pytest.raises(Exception, match="own machine"):
        enforce_device_identity(Request(cfg, principal=principal), "research-laptop")


def test_sensitive_routes_require_the_right_principal():
    cfg = settings(api_auth_required=True)
    token, _ = issue_dashboard_token(cfg)
    operator = authenticate_request(Request(cfg, {"authorization": f"Bearer {token}"}), cfg)
    require_human_operator(Request(cfg, principal=operator))
    require_fleet_controller(Request(cfg, principal=operator))
    device_token = cfg.device_api_tokens()["dev-laptop"]
    device = authenticate_request(
        Request(cfg, {"authorization": f"Bearer {device_token}", "x-ai-ops-device-id": "dev-laptop"}),
        cfg,
    )
    with pytest.raises(Exception, match="human operator"):
        require_human_operator(Request(cfg, principal=device))
    with pytest.raises(Exception, match="fleet-controller"):
        require_fleet_controller(Request(cfg, principal=device))
