import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.bot.app import build_bot, build_dispatcher
from app.core.config import settings

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / 'runtime'
STATE_PATH = STATE_DIR / 'bot_status.json'
HEARTBEAT_INTERVAL_SECONDS = 15



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def write_bot_state(payload: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def heartbeat_loop(state: dict):
    while True:
        state['status'] = 'running'
        state['last_heartbeat_at'] = utc_now_iso()
        write_bot_state(state)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def main():
    dispatcher = build_dispatcher()
    bot = build_bot()
    state = {
        'service': 'bot',
        'status': 'starting',
        'started_at': utc_now_iso(),
        'last_heartbeat_at': None,
        'last_success_at': None,
        'last_failure_at': None,
        'last_error': None,
        'runtime_mode': settings.runtime_mode,
    }
    write_bot_state(state)
    if settings.runtime_mode != 'live':
        state['status'] = 'idle'
        state['last_success_at'] = utc_now_iso()
        state['last_heartbeat_at'] = state['last_success_at']
        write_bot_state(state)
        print('Bot layer configured in non-live mode; dispatcher assembled successfully.')
        return

    heartbeat_task = asyncio.create_task(heartbeat_loop(state))
    try:
        state['status'] = 'running'
        state['last_success_at'] = utc_now_iso()
        state['last_heartbeat_at'] = state['last_success_at']
        write_bot_state(state)
        await dispatcher.start_polling(bot)
    except Exception as exc:  # pragma: no cover - runtime protection
        state['status'] = 'degraded'
        state['last_failure_at'] = utc_now_iso()
        state['last_heartbeat_at'] = state['last_failure_at']
        state['last_error'] = str(exc)
        write_bot_state(state)
        raise
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task


if __name__ == '__main__':
    import contextlib

    asyncio.run(main())
