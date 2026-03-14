from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_CHECKLIST = ROOT / 'RELEASE_CHECKLIST.md'
GO_NO_GO_CHECK = ROOT / 'GO_NO_GO_CHECK.md'
RELEASE_RECORD_TEMPLATE = ROOT / 'release_records' / 'TEMPLATE.md'


def test_release_update_script_enforces_non_root_and_secret_file_policy():
    script = (ROOT / 'scripts' / 'release_update.sh').read_text()
    assert 'Run this script as the runtime user' in script
    assert 'must not contain inline TELEGRAM_BOT_TOKEN' in script
    assert 'TELEGRAM_BOT_TOKEN_FILE' in script


def test_release_update_script_requires_deterministic_git_state_or_release_ref():
    script = (ROOT / 'scripts' / 'release_update.sh').read_text()
    assert 'Detached HEAD detected. Set RELEASE_REF explicitly' in script
    assert 'git fetch --all --tags --prune' in script
    assert 'git pull --ff-only origin' in script


def test_release_update_script_runs_migrations_and_smoke_check():
    script = (ROOT / 'scripts' / 'release_update.sh').read_text()
    assert 'alembic upgrade head' in script
    assert 'curl --fail --silent --show-error' in script
    assert 'docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up --build -d --remove-orphans' in script


def test_release_docs_define_mandatory_operational_gate():
    checklist = RELEASE_CHECKLIST.read_text()
    assert 'release_records/YYYY-MM-DD-<release-marker>.md' in checklist
    assert 'Если хотя бы один пункт не выполнен — решение автоматически `NO-GO`.' in checklist
    assert 'Mandatory post-deploy gate' in checklist

    go_no_go = GO_NO_GO_CHECK.read_text()
    assert 'RELEASE_CHECKLIST.md' in go_no_go
    assert 'Без release record решение считается **непринятым**' in go_no_go


def test_release_record_template_exists_for_real_sign_off_usage():
    template = RELEASE_RECORD_TEMPLATE.read_text()
    assert 'Final decision: <GO|NO-GO>' in template
    assert 'Human explicitly approves GO: <yes|no>' in template
    assert './scripts/release_update.sh' in template
