from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal


class Settings(BaseSettings):
    ENV: Literal["dev", "prod"] = "dev"

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["plain", "json"] = "json"
    APP_NAME: str = "fujida_agent"
    REQUEST_ID_HEADER: str = "x-request-id"
    UVICORN_ACCESS_LOG: bool = False

    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str | None = None
    WEBHOOK_URL: str
    
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str
    
    GOOGLE_SHEETS_CREDS: str
    GOOGLE_SHEETS_NAME: str
    
    GREEN_API_URL: str
    GREEN_API_INSTANCE_ID: int
    GREEN_API_TOKEN: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _normalize_level(cls, v: str) -> str:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("LOG_FORMAT", mode="before")
    @classmethod
    def _normalize_format(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


config = Settings()
