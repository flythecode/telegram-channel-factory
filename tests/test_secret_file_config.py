from pathlib import Path

import pytest

from app.core.config import Settings


def test_settings_can_load_telegram_token_from_secret_file(tmp_path):
    secret_file = tmp_path / "telegram_bot_token"
    secret_file.write_text(" 123:abc-token \n", encoding="utf-8")

    settings = Settings(
        runtime_mode="live",
        publisher_backend="telegram",
        telegram_bot_token_file=str(secret_file),
    )

    assert settings.telegram_bot_token == "123:abc-token"


def test_explicit_env_value_wins_over_secret_file(tmp_path):
    secret_file = tmp_path / "telegram_bot_token"
    secret_file.write_text("file-token\n", encoding="utf-8")

    settings = Settings(
        runtime_mode="live",
        publisher_backend="telegram",
        telegram_bot_token="env-token",
        telegram_bot_token_file=str(secret_file),
    )

    assert settings.telegram_bot_token == "env-token"


def test_missing_secret_file_fails_fast(tmp_path):
    missing = tmp_path / "missing_token_file"

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN_FILE must point to an existing file"):
        Settings(
            runtime_mode="live",
            publisher_backend="telegram",
            telegram_bot_token_file=str(missing),
        )
