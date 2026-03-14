import json
from datetime import datetime, timedelta, timezone
from pathlib import Path



def test_check_api_status_reports_unhealthy_on_exception(monkeypatch):
    from scripts import check_api_status as module

    def _boom(*args, **kwargs):
        raise RuntimeError('connection refused')

    monkeypatch.setattr(module, 'urlopen', _boom)
    assert module.main() == 1



def test_check_bot_status_ok_for_idle_non_live(tmp_path):
    from scripts import check_bot_status as module

    state_path = tmp_path / 'bot_status.json'
    state_path.write_text(
        json.dumps(
            {
                'status': 'idle',
                'runtime_mode': 'stub',
                'last_heartbeat_at': datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding='utf-8',
    )
    module.STATE_PATH = state_path
    assert module.main() == 0



def test_check_bot_status_fails_for_stale_live_heartbeat(tmp_path):
    from scripts import check_bot_status as module

    state_path = tmp_path / 'bot_status.json'
    state_path.write_text(
        json.dumps(
            {
                'status': 'running',
                'runtime_mode': 'live',
                'last_heartbeat_at': (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                'last_error': None,
            }
        ),
        encoding='utf-8',
    )
    module.STATE_PATH = state_path
    assert module.main() == 1



def test_check_runtime_alerts_marks_failed_services(monkeypatch, tmp_path):
    from scripts import check_runtime_alerts as module

    alerts_path = tmp_path / 'alerts_status.json'
    module.ALERTS_PATH = alerts_path
    monkeypatch.setattr(module.check_api_status, 'main', lambda: 0)
    monkeypatch.setattr(module.check_worker_status, 'main', lambda: 1)
    monkeypatch.setattr(module.check_bot_status, 'main', lambda: 0)

    assert module.main() == 1
    payload = json.loads(alerts_path.read_text(encoding='utf-8'))
    assert payload['status'] == 'alert'
    assert payload['failed'] == ['worker']
