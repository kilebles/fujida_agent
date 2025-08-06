from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):  
    ENV: Literal["dev", "prod"] = "dev"

    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str | None = None
    WEBHOOK_URL: str

    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


config = Settings()
