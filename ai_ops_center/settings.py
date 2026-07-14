from functools import lru_cache
import json
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql://aiops:aiops@localhost:5432/aiops"
    local_database_url: str = "postgresql://aiops:aiops@localhost:5432/aiops"
    ollama_base_url: str = "http://localhost:11434"
    llm_router_url: str = "http://localhost:8091"
    openwebui_url: str = "http://localhost:3000"
    n8n_url: str = "http://localhost:5678"
    local_n8n_url: str = "http://localhost:5678"
    flowise_url: str = ""
    local_flowise_url: str = "http://localhost:3001"
    flowise_api_key: str = ""
    n8n_webhook_url: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    groq_model: str = "llama-3.1-8b-instant"
    anthropic_model: str = "claude-3-haiku-20240307"
    google_model: str = "gemini-2.0-flash"
    worker_machine_id: str = "brain-gaming-pc"
    worker_sleep_seconds: int = 10
    worker_work_seconds: int = 4
    brain_instruction_secret: str = ""
    report_timezone: str = "America/Chicago"
    brain_host: str = "100.70.49.32"
    github_owner: str = "bluejay88"
    github_repo: str = "AI-Operations-center"
    github_default_branch: str = "master"
    github_repo_url: str = "https://github.com/bluejay88/AI-Operations-center.git"
    human_approval_required: bool = Field(default=True)
    expose_api_docs: bool = True
    # Authentication is fail-closed in production. Secrets must be injected by
    # the local .env/secret store and never have repository defaults.
    api_auth_required: bool = False
    api_control_token: str = ""
    device_api_tokens_json: str = "{}"
    dashboard_password: str = ""
    dashboard_password_hash: str = ""
    dashboard_session_secret: str = ""
    dashboard_session_ttl_seconds: int = 3600
    cors_allow_origins: str = "http://localhost:8088,http://127.0.0.1:8088,http://100.70.49.32:8088,null"
    cors_allow_origin_regex: str = r"^https://.*\.netlify\.app$|^http://localhost(:\d+)?$|^http://127\.0\.0\.1(:\d+)?$|^http://100\.[0-9.]+(:\d+)?$"

    @property
    def control_plane_auth_required(self) -> bool:
        return self.api_auth_required or self.app_env.strip().lower() == "production"

    def device_api_tokens(self) -> dict[str, str]:
        try:
            parsed = json.loads(self.device_api_tokens_json or "{}")
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(machine_id): str(token)
            for machine_id, token in parsed.items()
            if isinstance(machine_id, str) and isinstance(token, str) and token
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
