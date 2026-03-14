import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.worker import process_publication_batch_with_summary  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
logger = logging.getLogger(__name__)

STATE_DIR = ROOT / 'runtime'
STATE_PATH = STATE_DIR / 'worker_status.json'



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def write_worker_state(payload: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')



def build_base_state() -> dict:
    return {
        'service': 'worker',
        'status': 'starting',
        'started_at': utc_now_iso(),
        'last_heartbeat_at': None,
        'last_success_at': None,
        'last_failure_at': None,
        'last_error': None,
        'consecutive_failures': 0,
        'last_summary': None,
        'poll_interval_seconds': settings.worker_poll_interval_seconds,
    }


if __name__ == '__main__':
    state = build_base_state()
    write_worker_state(state)
    logger.info('worker runtime started', extra={'state_path': str(STATE_PATH)})
    while True:
        db = SessionLocal()
        try:
            summary = process_publication_batch_with_summary(db)
            state['status'] = 'running'
            state['last_heartbeat_at'] = utc_now_iso()
            state['last_success_at'] = state['last_heartbeat_at']
            state['last_error'] = None
            state['consecutive_failures'] = 0
            state['last_summary'] = summary.to_dict()
            write_worker_state(state)
            logger.info('worker cycle complete', extra=summary.to_dict())
        except Exception as exc:  # pragma: no cover - runtime protection
            state['status'] = 'degraded'
            state['last_heartbeat_at'] = utc_now_iso()
            state['last_failure_at'] = state['last_heartbeat_at']
            state['last_error'] = str(exc)
            state['consecutive_failures'] += 1
            write_worker_state(state)
            logger.exception(
                'worker cycle failed',
                extra={
                    'error': str(exc),
                    'consecutive_failures': state['consecutive_failures'],
                    'state_path': str(STATE_PATH),
                },
            )
        finally:
            db.close()
        time.sleep(settings.worker_poll_interval_seconds)
