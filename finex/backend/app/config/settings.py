from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "FinEx Backend"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    host: str = "127.0.0.1"
    port: int = 8000

    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    databricks_host: str = ""
    databricks_token: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = "finex_dev"
    databricks_schema: str = "core"

    embedding_model: str = "bge-large-en-v1.5"
    llm_provider: str = "openai"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
