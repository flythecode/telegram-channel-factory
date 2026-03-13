from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tracked_telegram_env_template_contains_no_real_token_placeholder_value():
    telegram_env = (ROOT / '.env.telegram-test').read_text()
    assert 'PUT_REAL_BOT_TOKEN_HERE' not in telegram_env
    assert 'SET_IN_LOCAL_UNTRACKED_ENV_ONLY' in telegram_env


def test_gitignore_protects_live_secret_files():
    gitignore = (ROOT / '.gitignore').read_text()
    assert '.env.live' in gitignore
    assert 'secrets/' in gitignore
