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

    llm_provider: str = "stub"
    llm_api_key: str | None = None
    llm_api_key_file: str | None = None
    llm_model_default: str = "stub-default"
    llm_base_url: str | None = None
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    llm_retry_base_delay_ms: int = 500
    llm_retry_max_delay_ms: int = 8000
    llm_circuit_breaker_threshold: int = 3
    llm_circuit_breaker_cooldown_seconds: int = 30
    llm_routing_strategy: str = "single-model"
    llm_fallback_provider: str | None = None
    llm_fallback_model: str | None = None
    llm_failover_strategy: str = "graceful-degradation"

    worker_poll_interval_seconds: int = 5
    worker_batch_limit: int = 100
    generation_worker_pool_size: int = 4
    generation_job_batch_limit: int = 100
    generation_project_concurrency_limit: int = 1
    generation_client_concurrency_limit: int = 2
    generation_global_rate_limit_per_window: int = 50
    generation_project_rate_limit_per_window: int = 5
    generation_client_rate_limit_per_window: int = 15
    generation_rate_limit_window_seconds: int = 60

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

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        allowed = {"stub", "openai", "anthropic", "openrouter", "gemini"}
        if value not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("llm_routing_strategy")
    @classmethod
    def validate_llm_routing_strategy(cls, value: str) -> str:
        allowed = {"single-model", "by-operation", "tiered"}
        if value not in allowed:
            raise ValueError(f"LLM_ROUTING_STRATEGY must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("llm_failover_strategy")
    @classmethod
    def validate_llm_failover_strategy(cls, value: str) -> str:
        allowed = {"disabled", "fallback-provider", "graceful-degradation"}
        if value not in allowed:
            raise ValueError(f"LLM_FAILOVER_STRATEGY must be one of: {', '.join(sorted(allowed))}")
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

        if not self.llm_api_key and self.llm_api_key_file:
            llm_key_path = Path(self.llm_api_key_file)
            if not llm_key_path.is_file():
                raise ValueError("LLM_API_KEY_FILE must point to an existing file")
            self.llm_api_key = llm_key_path.read_text(encoding="utf-8").strip()

        if self.llm_api_key is not None:
            self.llm_api_key = self.llm_api_key.strip() or None

        if self.llm_base_url is not None:
            self.llm_base_url = self.llm_base_url.strip() or None

        if self.llm_model_default is not None:
            self.llm_model_default = self.llm_model_default.strip()
            if not self.llm_model_default:
                raise ValueError("LLM_MODEL_DEFAULT must not be empty")

        if self.llm_fallback_provider is not None:
            self.llm_fallback_provider = self.llm_fallback_provider.strip().lower() or None
            allowed = {"stub", "openai", "anthropic", "openrouter", "gemini"}
            if self.llm_fallback_provider and self.llm_fallback_provider not in allowed:
                raise ValueError(f"LLM_FALLBACK_PROVIDER must be one of: {', '.join(sorted(allowed))}")

        if self.llm_fallback_model is not None:
            self.llm_fallback_model = self.llm_fallback_model.strip() or None

        if self.llm_timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be greater than 0")

        if self.llm_max_retries < 0:
            raise ValueError("LLM_MAX_RETRIES must be greater than or equal to 0")

        if self.llm_retry_base_delay_ms <= 0:
            raise ValueError("LLM_RETRY_BASE_DELAY_MS must be greater than 0")

        if self.llm_retry_max_delay_ms < self.llm_retry_base_delay_ms:
            raise ValueError("LLM_RETRY_MAX_DELAY_MS must be greater than or equal to LLM_RETRY_BASE_DELAY_MS")

        if self.llm_circuit_breaker_threshold <= 0:
            raise ValueError("LLM_CIRCUIT_BREAKER_THRESHOLD must be greater than 0")

        if self.llm_circuit_breaker_cooldown_seconds <= 0:
            raise ValueError("LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS must be greater than 0")

        if self.generation_worker_pool_size <= 0:
            raise ValueError("GENERATION_WORKER_POOL_SIZE must be greater than 0")

        if self.generation_job_batch_limit <= 0:
            raise ValueError("GENERATION_JOB_BATCH_LIMIT must be greater than 0")

        if self.generation_project_concurrency_limit <= 0:
            raise ValueError("GENERATION_PROJECT_CONCURRENCY_LIMIT must be greater than 0")

        if self.generation_client_concurrency_limit <= 0:
            raise ValueError("GENERATION_CLIENT_CONCURRENCY_LIMIT must be greater than 0")

        if self.generation_global_rate_limit_per_window <= 0:
            raise ValueError("GENERATION_GLOBAL_RATE_LIMIT_PER_WINDOW must be greater than 0")

        if self.generation_project_rate_limit_per_window <= 0:
            raise ValueError("GENERATION_PROJECT_RATE_LIMIT_PER_WINDOW must be greater than 0")

        if self.generation_client_rate_limit_per_window <= 0:
            raise ValueError("GENERATION_CLIENT_RATE_LIMIT_PER_WINDOW must be greater than 0")

        if self.generation_rate_limit_window_seconds <= 0:
            raise ValueError("GENERATION_RATE_LIMIT_WINDOW_SECONDS must be greater than 0")

        if self.llm_provider != "stub" and not self.llm_api_key:
            raise ValueError("LLM_PROVIDER requires LLM_API_KEY or LLM_API_KEY_FILE unless provider=stub")

        if self.llm_failover_strategy == "fallback-provider" and not self.llm_fallback_provider:
            raise ValueError("LLM_FAILOVER_STRATEGY=fallback-provider requires LLM_FALLBACK_PROVIDER")

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
