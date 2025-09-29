"""Application configuration using Pydantic settings."""

import json
from typing import Union

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: str = Field(default="development", description="Application environment")
    app_log_level: str = Field(default="INFO", description="Log level")
    app_debug: bool = Field(default=False, description="Debug mode")

    # --- Database ---
    database_url: str = Field(
        description="Database connection URL",
        examples=["postgresql+asyncpg://user:pass@localhost:5432/db"],
    )
    database_pool_size: int = Field(default=20, description="Database pool size")
    database_max_overflow: int = Field(default=30, description="Database max overflow")

    # --- Redis ---
    redis_url: str = Field(
        description="Redis connection URL",
        examples=["redis://localhost:6379/0"],
    )
    redis_max_connections: int = Field(default=20, description="Redis max connections")

    # --- Celery ---
    celery_broker_url: str = Field(description="Celery broker URL")
    celery_result_backend: str = Field(description="Celery result backend URL")
    celery_task_serializer: str = Field(default="json", description="Celery task serializer")
    celery_result_serializer: str = Field(default="json", description="Celery result serializer")

    # --- Security ---
    secret_key: str = Field(description="Secret key for signing")

    # Allow JSON list or comma-separated string from env (CORS_ORIGINS / cors_origins)
    cors_origins: Union[list[str], str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="CORS allowed origins",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    # --- Health checks ---
    health_check_timeout: int = Field(default=2, description="Health check timeout in seconds")

    # --- Uvicorn Settings ---
    uvicorn_reload: bool = Field(default=False, description="Enable Uvicorn auto-reload")
    watchfiles_force_polling: int = Field(default=1, description="Force polling for file changes on Windows")

    # --- Pagination ---
    page_size_default: int = Field(default=20, description="Default page size for pagination")
    page_size_max: int = Field(default=100, description="Maximum page size for pagination")

    # --- Tenant Settings ---
    tenant_reserved_slugs: str = Field(
        default="api,admin,www,app,support,help,docs,status",
        description="Comma-separated list of reserved tenant slugs"
    )

    # --- Validators ---
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        """Parse cors_origins from JSON or CSV string."""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            # Try JSON first
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed]
            except Exception:
                pass
            # Fallback to CSV
            return [p.strip() for p in s.split(",") if p.strip()]
        return [str(v).strip()]

    # --- Helpers ---
    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def reserved_slugs_set(self) -> set[str]:
        """Get reserved slugs as a set."""
        return {slug.strip().lower() for slug in self.tenant_reserved_slugs.split(",") if slug.strip()}


# Global settings instance
settings = Settings()
