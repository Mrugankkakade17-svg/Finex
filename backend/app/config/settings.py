from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Any, ClassVar, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigurationError

BASE_DIR = Path(__file__).resolve().parents[2]


class AppEnv(str, Enum):
    """Supported FinEx runtime environments."""

    LOCAL = "local"
    DEV = "dev"
    UAT = "uat"
    PROD = "prod"

    @classmethod
    def from_string(cls, value: str) -> "AppEnv":
        aliases = {
            "development": cls.DEV,
            "dev": cls.DEV,
            "local": cls.LOCAL,
            "test": cls.LOCAL,
            "testing": cls.LOCAL,
            "uat": cls.UAT,
            "prod": cls.PROD,
            "production": cls.PROD,
        }
        normalized = value.strip().lower()
        if normalized in aliases:
            return aliases[normalized]
        raise ConfigurationError(
            f"Invalid APP_ENV '{value}'. Valid values are: local, dev, uat, prod."
        )


class Settings(BaseSettings):
    """Typed, safe configuration for local through production-like environments."""

    app_name: str = "FinEx Backend"
    app_version: str = "0.1.0"
    app_env: AppEnv = AppEnv.LOCAL
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    api_base_url: str = "http://localhost:8000"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Correlation-ID"]
    )

    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    local_app_enabled: bool = False
    local_db_path: Path = BASE_DIR / ".local" / "finex.sqlite3"
    local_session_ttl_minutes: int = Field(default=30, ge=1, le=60, strict=True)

    databricks_host: str = ""
    databricks_token: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = "finex_dev"
    databricks_schema: str = "core"

    embedding_model: str = "bge-large-en-v1.5"
    llm_provider: str = "openai"
    openai_api_key: str = ""

    market_data_provider: str = "mock"
    market_data_api_key: str = ""

    log_level: str = "INFO"

    SENSITIVE_FIELDS: ClassVar[set[str]] = {
        "secret_key",
        "databricks_token",
        "openai_api_key",
        "market_data_api_key",
        "password",
        "token",
        "access_token",
    }
    PLACEHOLDER_SECRET_PREFIXES: ClassVar[tuple[str, ...]] = (
        "change-me",
        "change_me",
        "placeholder",
        "replace-",
        "replace_",
        "your-",
        "your_",
    )

    # Local-only deterministic fixture adapter. Never enable in UAT or production.
    fixture_mode: Literal["disabled", "s1_dat_01", "s2_dat_01"] = "disabled"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        enable_decoding=False,
        extra="ignore",
    )

    @property
    def is_production_like(self) -> bool:
        return self.app_env in {AppEnv.UAT, AppEnv.PROD}

    @field_validator("app_env", mode="before")
    @classmethod
    def validate_app_env(cls, value: Any) -> AppEnv:
        if isinstance(value, AppEnv):
            return value
        if isinstance(value, str):
            return AppEnv.from_string(value)
        raise ConfigurationError("APP_ENV must be a string.")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(origin).strip().rstrip("/") for origin in value if str(origin).strip()]
        if not isinstance(value, str):
            raise ConfigurationError("ALLOWED_ORIGINS must be a list or comma-separated string.")

        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ConfigurationError("ALLOWED_ORIGINS is not valid JSON.") from error
            if not isinstance(parsed, list):
                raise ConfigurationError("ALLOWED_ORIGINS JSON value must be a list.")
            return [str(origin).strip().rstrip("/") for origin in parsed if str(origin).strip()]
        return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError(
                "API_BASE_URL must be an absolute http:// or https:// URL with a host."
            )
        return normalized

    @field_validator("local_session_ttl_minutes", mode="before")
    @classmethod
    def parse_local_ttl(cls, value: Any) -> Any:
        # Environment settings arrive as strings; other coercions remain forbidden.
        if isinstance(value, str) and value.strip().isdecimal():
            return int(value.strip())
        return value

    @field_validator("local_db_path", mode="before")
    @classmethod
    def require_native_file(cls, value: Any) -> Any:
        if str(value) == ":memory:" or str(value).startswith("file:"):
            raise ValueError("LOCAL_DB_PATH must select a native persistent file, not a URI.")
        return value

    @model_validator(mode="after")
    def validate_security_rules(self) -> "Settings":
        wildcard = "*" in self.allowed_origins

        if self.local_app_enabled:

            def is_loopback(hostname: str | None) -> bool:
                if hostname == "localhost":
                    return True
                try:
                    return bool(hostname and ip_address(hostname).is_loopback)
                except ValueError:
                    return False

            if not is_loopback(self.host) or not self.allowed_origins:
                raise ConfigurationError("Local application requires loopback host and origins.")
            for origin in self.allowed_origins:
                try:
                    parsed = urlparse(origin)
                    port = parsed.port
                except ValueError:
                    raise ConfigurationError(
                        "Local application requires valid loopback origins."
                    ) from None
                if (
                    parsed.scheme not in {"http", "https"}
                    or not is_loopback(parsed.hostname)
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                    or parsed.path not in {"", "/"}
                    or port == 0
                ):
                    raise ConfigurationError(
                        "Local application requires explicit loopback origins."
                    )

        if self.is_production_like and self.fixture_mode != "disabled":
            raise ValueError("fixture_mode must be disabled in UAT and production")
        if wildcard and self.allow_credentials:
            raise ConfigurationError(
                "Wildcard ALLOWED_ORIGINS cannot be combined with ALLOW_CREDENTIALS=true."
            )
        if self.is_production_like and wildcard:
            raise ConfigurationError(
                "Wildcard ALLOWED_ORIGINS are forbidden in UAT and production."
            )
        if self.is_production_like and "allowed_origins" not in self.model_fields_set:
            raise ConfigurationError(
                "ALLOWED_ORIGINS must be explicitly set in UAT and production."
            )
        if self.is_production_like and not self.allowed_origins:
            raise ConfigurationError("ALLOWED_ORIGINS must be explicit in UAT and production.")
        if self.is_production_like and self.debug:
            raise ConfigurationError("DEBUG must be false in UAT and production.")
        if self.is_production_like and not self.api_base_url.startswith("https://"):
            raise ConfigurationError("API_BASE_URL must use HTTPS in UAT and production.")

        for origin in self.allowed_origins:
            if origin == "*":
                continue
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ConfigurationError(f"ALLOWED_ORIGINS contains an invalid origin: '{origin}'.")

        if self.is_production_like:
            insecure_values = {"", "changeme", "secret", "test", "your_secret_key"}
            normalized_secret_key = self.secret_key.strip().lower()
            is_placeholder_secret = normalized_secret_key.startswith(
                self.PLACEHOLDER_SECRET_PREFIXES
            )
            if (
                normalized_secret_key in insecure_values
                or is_placeholder_secret
                or len(normalized_secret_key) < 32
            ):
                raise ConfigurationError(
                    "SECRET_KEY must be explicitly configured with a non-placeholder value "
                    "of at least 32 characters in UAT and production."
                )
            if self.llm_provider.lower() == "openai" and not self.openai_api_key:
                raise ConfigurationError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai in UAT and production."
                )
            if (
                self.market_data_provider.lower() in {"alpha_vantage", "polygon"}
                and not self.market_data_api_key
            ):
                raise ConfigurationError(
                    "MARKET_DATA_API_KEY is required for the selected market provider "
                    "in UAT and production."
                )
        return self

    def redacted_dict(self) -> dict[str, Any]:
        values = self.model_dump()
        for field_name in values:
            if any(secret_name in field_name.lower() for secret_name in self.SENSITIVE_FIELDS):
                values[field_name] = "[REDACTED]" if values[field_name] else ""
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
