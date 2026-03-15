from pathlib import Path

import pytest

from app.core.config import Settings


def test_stub_llm_provider_allows_empty_key():
    settings = Settings(llm_provider="stub")

    assert settings.llm_provider == "stub"
    assert settings.llm_api_key is None


def test_settings_can_load_llm_key_from_secret_file(tmp_path):
    secret_file = tmp_path / "llm_api_key"
    secret_file.write_text(" sk-test-key \n", encoding="utf-8")

    settings = Settings(
        llm_provider="openai",
        llm_api_key_file=str(secret_file),
        llm_model_default="gpt-4.1-mini",
    )

    assert settings.llm_api_key == "sk-test-key"


def test_non_stub_llm_provider_requires_api_key():
    with pytest.raises(ValueError, match="LLM_PROVIDER requires LLM_API_KEY or LLM_API_KEY_FILE unless provider=stub"):
        Settings(llm_provider="openai", llm_model_default="gpt-4.1-mini")


def test_missing_llm_secret_file_fails_fast(tmp_path):
    missing = tmp_path / "missing_llm_key"

    with pytest.raises(ValueError, match="LLM_API_KEY_FILE must point to an existing file"):
        Settings(
            llm_provider="anthropic",
            llm_api_key_file=str(missing),
            llm_model_default="claude-3-5-sonnet",
        )


def test_llm_model_default_must_not_be_empty():
    with pytest.raises(ValueError, match="LLM_MODEL_DEFAULT must not be empty"):
        Settings(llm_provider="stub", llm_model_default="   ")


def test_llm_timeout_must_be_positive():
    with pytest.raises(ValueError, match="LLM_TIMEOUT_SECONDS must be greater than 0"):
        Settings(llm_provider="stub", llm_timeout_seconds=0)


def test_llm_max_retries_must_be_non_negative():
    with pytest.raises(ValueError, match="LLM_MAX_RETRIES must be greater than or equal to 0"):
        Settings(llm_provider="stub", llm_max_retries=-1)


def test_failover_strategy_requires_fallback_provider_when_configured():
    with pytest.raises(ValueError, match='LLM_FAILOVER_STRATEGY=fallback-provider requires LLM_FALLBACK_PROVIDER'):
        Settings(
            llm_provider='stub',
            llm_failover_strategy='fallback-provider',
        )


def test_settings_accept_graceful_degradation_defaults():
    settings = Settings(
        llm_provider='stub',
        llm_failover_strategy='graceful-degradation',
        llm_fallback_provider=' stub ',
        llm_fallback_model=' stub-fallback ',
    )

    assert settings.llm_failover_strategy == 'graceful-degradation'
    assert settings.llm_fallback_provider == 'stub'
    assert settings.llm_fallback_model == 'stub-fallback'
