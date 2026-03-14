import json
from datetime import datetime, timezone
from pathlib import Path

from scripts import check_api_status, check_bot_status, check_worker_status

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / 'runtime'
ALERTS_PATH = STATE_DIR / 'alerts_status.json'



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def write_alert_state(payload: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ALERTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')



def main() -> int:
    checks = {
        'api': check_api_status.main(),
        'worker': check_worker_status.main(),
        'bot': check_bot_status.main(),
    }
    failed = [name for name, code in checks.items() if code != 0]
    payload = {
        'service': 'runtime-alerts',
        'checked_at': utc_now_iso(),
        'checks': checks,
        'failed': failed,
        'status': 'alert' if failed else 'ok',
    }
    write_alert_state(payload)
    if failed:
        print(f'alerts active: {", ".join(failed)}')
        return 1
    print('alerts clear')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
