"""Application settings.

Loaded from environment variables and the repository-root ``.env`` file. Secrets never leave the
server: the settings API exposes :meth:`Settings.public_view` which masks them.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
SECRET_FIELDS = {
    "secret_key",
    "neo4j_password",
    "brave_api_key",
    "serper_api_key",
    "tavily_api_key",
    "github_token",
    "telegram_bot_token",
    "smtp_password",
    "alert_webhook_url",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General
    eyohe_env: Literal["development", "production", "test"] = "development"
    secret_key: str = "dev-only-insecure-secret-change-me"  # noqa: S105 - overridden by .env
    api_host: str = "0.0.0.0"  # noqa: S104 - bound inside the user's own workstation/container
    api_port: int = 8000
    public_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_json: bool = True

    # Storage
    database_url: str = "sqlite+aiosqlite:///./data/eyohe.sqlite3"
    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = Path("./data")
    evidence_retention_days: int = 0
    snapshot_max_text_chars: int = 200_000

    # Jobs / graph
    job_backend: Literal["embedded", "arq"] = "embedded"
    graph_backend: Literal["postgresql", "neo4j"] = "postgresql"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # AI
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout_seconds: int = 180
    ollama_num_ctx: int = 16384

    # Search
    search_providers: str = "searxng"
    searxng_url: str = "http://localhost:8080"
    brave_api_key: str = ""
    serper_api_key: str = ""
    tavily_api_key: str = ""

    # Collectors
    github_token: str = ""
    reddit_user_agent: str = "eyohe-osint/0.1 (public research tool)"
    user_agent: str = "Mozilla/5.0 (compatible; EyoheOSINT/0.1; +https://localhost/eyohe)"

    # Bounds
    max_agent_iterations: int = 50
    max_research_depth: int = 2
    max_queries: int = 40
    max_pages: int = 60
    max_runtime_seconds: int = 1800
    max_results_per_source: int = 20
    max_results: int = 100
    request_timeout: int = 20
    max_fetch_bytes: int = 5_000_000

    # Security
    session_ttl_hours: int = 24
    cookie_secure: bool = False
    allow_private_network_fetch: bool = False
    rate_limit_per_minute: int = 240
    auth_rate_limit_per_minute: int = 10

    # Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    alert_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Reports / tools
    report_classification: Literal["INTERNAL", "RESEARCH", "CONFIDENTIAL"] = "RESEARCH"
    chromium_path: str = "/usr/bin/chromium"

    @field_validator("ollama_url", "searxng_url", "redis_url", "neo4j_uri", mode="after")
    @classmethod
    def _prefer_ipv4_loopback(cls, v: str) -> str:
        # On many Linux hosts "localhost" resolves only to ::1 while Ollama/Redis/SearXNG bind to
        # 127.0.0.1. Using the IPv4 loopback explicitly avoids confusing "connection refused" errors.
        return v.replace("://localhost:", "://127.0.0.1:").replace("://localhost/", "://127.0.0.1/")

    @field_validator("data_dir", mode="after")
    @classmethod
    def _abs_data_dir(cls, v: Path) -> Path:
        return v if v.is_absolute() else (REPO_ROOT / v).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def search_provider_list(self) -> list[str]:
        return [p.strip().lower() for p in self.search_providers.split(",") if p.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.eyohe_env == "production"

    def public_view(self) -> dict[str, object]:
        """Settings safe to show in the UI. Secrets are masked, never returned."""
        out: dict[str, object] = {}
        for name, value in self.model_dump().items():
            if name in SECRET_FIELDS:
                out[name] = "••••••" if value else ""
            elif name == "database_url":
                out[name] = _mask_dsn(str(value))
            else:
                out[name] = str(value) if isinstance(value, Path) else value
        return out


def _mask_dsn(dsn: str) -> str:
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        creds, host = rest.rsplit("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:••••@{host}"
    return dsn


@lru_cache
def get_settings() -> Settings:
    return Settings()
