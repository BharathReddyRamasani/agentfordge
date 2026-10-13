"""Central configuration. All runtime settings come from environment variables with safe defaults."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AgentForge"
    app_env: str = "development"
    secret_key: str = "agentforge-dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = f"sqlite:///{(BASE_DIR.parent / 'data' / 'agentforge.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_timeout: float = 120.0
    llm_max_retries: int = 2

    # Provider-specific credentials (never exposed, never stored — env only)
    opencode_zen_api_key: str = ""
    opencode_zen_base_url: str = "https://opencode.ai/zen/v1"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_referer: str = "http://localhost:8000"
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Explicit multi-provider fallback (empty = fail clearly, never silently switch)
    llm_primary_provider: str = ""
    llm_fallback_provider: str = ""
    llm_fallback_model: str = ""

    log_level: str = "INFO"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    embedding_provider: str = "tfidf"
    embedding_model: str = "text-embedding-3-small"
    rag_top_k: int = 8

    worker_poll_interval: float = 2.0
    worker_mode: str = "thread"
    sandbox_timeout: int = 300
    max_debug_iterations: int = 3
    max_agent_retries: int = 2

    workspace_dir: str = str(BASE_DIR.parent / "workspace")
    rag_dir: str = str(BASE_DIR.parent / "data" / "rag")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def sqlalchemy_connect_args(self) -> dict:
        if self.is_sqlite:
            return {"check_same_thread": False}
        return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
