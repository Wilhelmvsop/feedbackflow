from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_DEMO_PASSWORD = "feedbackflow-demo"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./feedbackflow.db"
    auto_migrate: bool = True
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Sessions
    token_ttl_hours: int = 24 * 7

    # Demo workspace
    seed_demo: bool = True
    demo_email: str = "demo@feedbackflow.local"
    demo_password: str = DEFAULT_DEMO_PASSWORD
    demo_workspace_slug: str = "demo"

    # Abuse protection (per client IP, per minute)
    login_rate_limit: int = 10
    public_feedback_rate_limit: int = 20

    # Optional model provider (OpenAI-compatible chat completions API)
    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4.1-mini"
    ai_timeout_seconds: float = 30

    # MCP server
    mcp_workspace_slug: str = "demo"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Hosting providers (Render, Heroku) hand out postgres:// URLs; SQLAlchemy needs an explicit driver.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @field_validator("ai_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def check_production_secrets(self):
        if self.app_env == "production" and self.seed_demo and self.demo_password == DEFAULT_DEMO_PASSWORD:
            raise ValueError("Set DEMO_PASSWORD (or SEED_DEMO=false) when APP_ENV=production")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
