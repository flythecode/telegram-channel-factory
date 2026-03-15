from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_staging_real_llm_env_template_requires_separate_secret_file_and_demo_runtime():
    env_template = (ROOT / '.env.staging-real.example').read_text()

    assert 'APP_ENV=staging' in env_template
    assert 'RUNTIME_MODE=demo' in env_template
    assert 'PUBLISHER_BACKEND=stub' in env_template
    assert 'LLM_PROVIDER=openai' in env_template
    assert 'LLM_API_KEY_FILE=/absolute/path/to/secrets/llm_api_key.staging' in env_template
    assert 'Do not reuse the production bot token file or production LLM secret path.' in env_template


def test_real_llm_staging_runbook_defines_ideas_and_draft_checks():
    runbook = (ROOT / 'STAGING_REAL_LLM_SCENARIO.md').read_text()

    assert 'generate_ideas(...)' in runbook
    assert 'create_draft' in runbook
    assert 'LLM_PROVIDER != stub' in runbook
    assert 'LLM_API_KEY_FILE' in runbook
    assert 'separate staging provider key confirmed' in runbook


def test_real_llm_staging_script_enforces_runtime_guardrails_and_usage_checks():
    script = (ROOT / 'scripts' / 'run_real_llm_staging_scenario.py').read_text()

    assert "settings.app_env == 'staging'" in script
    assert "settings.runtime_mode == 'demo'" in script
    assert "settings.publisher_backend == 'stub'" in script
    assert "settings.llm_provider != 'stub'" in script
    assert 'LLM_API_KEY_FILE is required for a separate staging provider key' in script
    assert 'must not match TELEGRAM_BOT_TOKEN_FILE' in script
    assert "'ideas' in usage_by_operation" in script
    assert "'draft' in usage_by_operation" in script
