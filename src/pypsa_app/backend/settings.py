"""Application configuration using environment variables"""

from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_V1_PREFIX = "/api/v1"
SESSION_COOKIE_NAME = "pypsa_session"

# Database pool settings (PostgreSQL only)
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 30
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 3600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    base_url: str = Field(
        default="http://localhost:5173",
        description="Publicly accessible URL of the application",
        json_schema_extra={"category": "Application"},
    )
    data_dir: str = Field(
        default="./data",
        description=(
            "File storage directory to store application data and network files"
        ),
        json_schema_extra={"category": "Application"},
    )

    @property
    def data_dir_path(self) -> Path:
        """Computed absolute path to data directory"""
        return Path(self.data_dir).resolve()

    @property
    def networks_path(self) -> Path:
        """Computed path to networks directory"""
        return self.data_dir_path / "networks"

    # Database
    database_url: str = Field(
        default="sqlite:///./data/pypsa-app.db",
        description="Database URL (SQLite and PostgreSQL is supported)",
        json_schema_extra={"category": "Database"},
    )

    # Authentication
    enable_auth: bool = Field(
        default=False,
        description="Enable GitHub OAuth authentication",
        json_schema_extra={"category": "Authentication"},
    )
    github_client_id: str | None = Field(
        default=None,
        description="GitHub OAuth app client ID (create at https://github.com/settings/developers)",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    github_client_secret: str | None = Field(
        default=None,
        description="GitHub OAuth app client secret",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    session_secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description=(
            "Secret key for session cookies (generate with: openssl rand -base64 32)"
        ),
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )
    session_ttl: int = Field(
        default=604800,
        description="Session time-to-live in seconds (default: 7 days)",
        json_schema_extra={"category": "Authentication", "depends_on": "enable_auth"},
    )

    # Networks
    max_upload_size_mb: int = Field(
        default=2000,
        description="Maximum network file upload size in megabytes",
        json_schema_extra={"category": "Networks"},
    )

    # Runs
    snakedispatch_sync_interval: float = Field(
        default=10.0,
        description="Interval in seconds between background Snakedispatch sync cycles",
        json_schema_extra={"category": "Runs"},
    )
    callback_url_allowed_domains: str = Field(
        default="",
        description=(
            "Comma-separated list of allowed domains for run callback URLs "
            "(e.g. hooks.myorg.dev,example.com). "
            "Callbacks are rejected unless the host matches. "
            "Empty disables callbacks entirely."
        ),
        json_schema_extra={"category": "Runs"},
    )

    @property
    def resolved_callback_domains(self) -> list[str]:
        """Parse CALLBACK_URL_ALLOWED_DOMAINS into a list of domain strings."""
        if not self.callback_url_allowed_domains:
            return []
        return [
            d.strip() for d in self.callback_url_allowed_domains.split(",") if d.strip()
        ]

    snakedispatch_backends: str | None = Field(
        default=None,
        description=(
            "Comma-separated list of Snakedispatch backends in name=url format "
            "(e.g. cluster-a=http://sd-a:8000,cluster-b=http://sd-b:8000)"
        ),
        json_schema_extra={"category": "Runs"},
    )

    @property
    def resolved_backends(self) -> list[dict[str, str]]:
        """Parse SNAKEDISPATCH_BACKENDS into a list of {name, url} dicts."""
        if not self.snakedispatch_backends:
            return []
        backends = []
        for raw_entry in self.snakedispatch_backends.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            if "=" not in entry:
                msg = (
                    f"Invalid SNAKEDISPATCH_BACKENDS entry '{entry}'. "
                    "Expected format: name=url"
                )
                raise ValueError(msg)
            name, url = entry.split("=", 1)
            backends.append({"name": name.strip(), "url": url.strip()})
        return backends

    # Caching
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL for caching (optional)",
        json_schema_extra={"category": "Redis"},
    )
    plot_cache_ttl: int = Field(
        default=86400,
        description="Time-to-live in seconds for plot cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    network_cache_ttl: int = Field(
        default=7200,
        description="Time-to-live in seconds for network cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    run_outputs_cache_ttl: int = Field(
        default=10800,
        description="Time-to-live in seconds for run output file list cache entries",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )
    max_cache_size_mb: int = Field(
        default=50,
        description="Maximum cache size in megabytes",
        json_schema_extra={"category": "Redis", "depends_on": "redis_url"},
    )

    # SMTP
    smtp_host: str | None = Field(
        default=None,
        description="SMTP server hostname (enables email notifications when set)",
        json_schema_extra={"category": "Email"},
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_username: str | None = Field(
        default=None,
        description="SMTP authentication username",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_password: str | None = Field(
        default=None,
        description="SMTP authentication password",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS/STARTTLS for SMTP connection",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )
    smtp_from_address: str = Field(
        default="noreply@pypsa-app.local",
        description="Sender email address for notifications",
        json_schema_extra={"category": "Email", "depends_on": "smtp_host"},
    )

    @property
    def smtp_enabled(self) -> bool:
        """Whether SMTP email notifications are configured."""
        return self.smtp_host is not None

    # AI
    anthropic_api_key: str | None = Field(
        default=None,
        description=("Anthropic API key for Claude-powered chat features (optional)"),
        json_schema_extra={"category": "AI"},
    )
    anthropic_base_url: str | None = Field(
        default=None,
        description=(
            "Anthropic API base URL. Leave unset for api.anthropic.com. "
            "Override to use an Anthropic-compatible provider "
            "(e.g. http://localhost:11434 for Ollama, "
            "https://openrouter.ai/api/v1 for OpenRouter, "
            "or a local llama.cpp server)."
        ),
        json_schema_extra={"category": "AI"},
    )
    llm_model_default: str = Field(
        default="qwen3.5:9b",
        description=(
            "Default model ID for the chat endpoint when the request omits "
            "`model`. Use a model available at the configured provider "
            "(e.g. `qwen3.5:9b` for Ollama, `claude-opus-4-7` for Anthropic)."
        ),
        json_schema_extra={"category": "AI"},
    )
    llm_thinking_enabled: bool = Field(
        default=False,
        description=(
            "Enable extended thinking in chat replies. Off by default because "
            "thinking tokens are counted against `max_tokens` and many local "
            "models waste output on visible reasoning. Note: not portable "
            "across all providers — Claude Opus 4.7 rejects the `enabled` "
            "shape and requires adaptive thinking instead."
        ),
        json_schema_extra={"category": "AI"},
    )
    llm_thinking_budget_tokens: int = Field(
        default=4000,
        description=(
            "Token budget passed to the provider when thinking is enabled. "
            "Ollama accepts but does not enforce this value; Anthropic "
            "classic-thinking models require it strictly less than max_tokens."
        ),
        json_schema_extra={"category": "AI", "depends_on": "llm_thinking_enabled"},
    )
    llm_max_tokens: int = Field(
        default=16000,
        description=(
            "Maximum tokens the model may generate per chat response "
            "(includes thinking tokens when thinking is enabled)."
        ),
        json_schema_extra={"category": "AI"},
    )
    llm_system_prompt: str = Field(
        default=(
            "You are a helpful assistant for PyPSA, an open-source energy "
            "system optimization framework. Keep replies concise and "
            "accurate. If you are unsure about something, say so rather "
            "than guessing."
        ),
        description="System prompt prepended to every chat conversation.",
        json_schema_extra={"category": "AI"},
    )

    # Development
    backend_only: bool = Field(
        default=False,
        description="Run backend only without serving the frontend",
        json_schema_extra={"category": "Development"},
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:5174",
        description=(
            "Comma-separated list of allowed CORS origins"
            " (only used in backend-only mode)"
        ),
        json_schema_extra={"category": "Development", "depends_on": "backend_only"},
    )

    @model_validator(mode="after")
    def validate_auth_settings(self) -> Self:
        if self.enable_auth and self.database_url.startswith("sqlite"):
            msg = (
                "Authentication requires PostgreSQL. "
                "SQLite does not support the features needed for multi-user auth. "
                "Either set ENABLE_AUTH=false or use a PostgreSQL DATABASE_URL."
            )
            raise ValueError(msg)

        if (
            self.enable_auth
            and self.session_secret_key == "dev-secret-key-change-in-production"  # noqa: S105
        ):
            msg = "Must set a secure SESSION_SECRET_KEY when authentication is enabled"
            raise ValueError(msg)
        return self


settings = Settings()
