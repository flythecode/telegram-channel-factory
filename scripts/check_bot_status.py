import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / 'runtime' / 'bot_status.json'
MAX_HEARTBEAT_AGE_SECONDS = 60



def parse_iso(raw: str | None):
    if not raw:
        return None
    return datetime.fromisoformat(raw)



def main() -> int:
    if not STATE_PATH.exists():
        print(f'bot status file missing: {STATE_PATH}')
        return 1

    payload = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    status = payload.get('status')
    heartbeat = parse_iso(payload.get('last_heartbeat_at'))
    runtime_mode = payload.get('runtime_mode')

    if runtime_mode != 'live' and status == 'idle':
        print(f'bot idle in {runtime_mode} mode')
        return 0

    if heartbeat is None:
        print('bot heartbeat missing')
        return 1

    age_seconds = (datetime.now(timezone.utc) - heartbeat).total_seconds()
    if status != 'running':
        print(f'bot unhealthy: status={status} last_error={payload.get("last_error")}')
        return 1
    if age_seconds > MAX_HEARTBEAT_AGE_SECONDS:
        print(f'bot heartbeat stale: age_seconds={round(age_seconds, 2)}')
        return 1

    print(f'bot healthy status={status} age_seconds={round(age_seconds, 2)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
