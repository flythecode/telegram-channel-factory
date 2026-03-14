from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Telegram Channel Factory"
    app_env: str = "dev"
    debug: bool = True

    api_v1_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tcf"

    runtime_mode: str = "stub"
    publisher_backend: str = "stub"
    telegram_bot_token: str | None = None
    telegram_bot_token_file: str | None = None
    telegram_request_timeout_seconds: int = 20

    worker_poll_interval_seconds: int = 5
    worker_batch_limit: int = 100

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        allowed = {"dev", "staging", "prod", "test"}
        if value not in allowed:
            raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("runtime_mode")
    @classmethod
    def validate_runtime_mode(cls, value: str) -> str:
        allowed = {"stub", "demo", "live"}
        if value not in allowed:
            raise ValueError(f"RUNTIME_MODE must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("publisher_backend")
    @classmethod
    def validate_publisher_backend(cls, value: str) -> str:
        allowed = {"stub", "telegram"}
        if value not in allowed:
            raise ValueError(f"PUBLISHER_BACKEND must be one of: {', '.join(sorted(allowed))}")
        return value

    @model_validator(mode="after")
    def load_secret_files(self):
        if not self.telegram_bot_token and self.telegram_bot_token_file:
            token_path = Path(self.telegram_bot_token_file)
            if not token_path.is_file():
                raise ValueError("TELEGRAM_BOT_TOKEN_FILE must point to an existing file")
            self.telegram_bot_token = token_path.read_text(encoding="utf-8").strip()

        if self.telegram_bot_token is not None:
            self.telegram_bot_token = self.telegram_bot_token.strip() or None

        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

if settings.runtime_mode == "stub":
    settings.publisher_backend = "stub"
elif settings.runtime_mode == "demo":
    settings.publisher_backend = "stub"
elif settings.runtime_mode == "live":
    if settings.publisher_backend != "telegram":
        raise ValueError("RUNTIME_MODE=live requires PUBLISHER_BACKEND=telegram")
    if not settings.telegram_bot_token:
        raise ValueError("RUNTIME_MODE=live requires TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN_FILE")
