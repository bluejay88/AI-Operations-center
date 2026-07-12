from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql://aiops:aiops@localhost:5432/aiops"
    local_database_url: str = "postgresql://aiops:aiops@localhost:5432/aiops"
    ollama_base_url: str = "http://localhost:11434"
    openwebui_url: str = "http://localhost:3000"
    n8n_url: str = "http://localhost:5678"
    local_n8n_url: str = "http://localhost:5678"
    flowise_url: str = ""
    local_flowise_url: str = "http://localhost:3001"
    flowise_api_key: str = ""
    worker_machine_id: str = "brain-gaming-pc"
    worker_sleep_seconds: int = 10
    report_timezone: str = "America/Chicago"
    brain_host: str = "100.70.49.32"
    human_approval_required: bool = Field(default=True)
    expose_api_docs: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
