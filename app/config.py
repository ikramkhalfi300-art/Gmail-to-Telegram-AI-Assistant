from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
from pathlib import Path

# يحدد مسار .env بالنسبة لموقع config.py
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    model_config = ConfigDict(
        extra="ignore",
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8"
    )

    # General
    app_env: str = "development"
    base_url: str = "http://localhost:8000"

    # Gmail
    gmail_client_id: str
    gmail_client_secret: str
    gmail_token_path: str = "token.json"
    gmail_scopes: str = "https://www.googleapis.com/auth/gmail.modify"

    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = "MySecretWebHook.123"

    # Anthropic
    anthropic_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./email_assistant.db"

    # Scheduler
    email_fetch_interval: int = 5
    max_emails_per_fetch: int = 10


@lru_cache()
def get_settings() -> Settings:
    return Settings()