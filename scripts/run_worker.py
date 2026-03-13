import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.worker import process_publication_batch  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logger.info('worker stub started')
    while True:
        db = SessionLocal()
        try:
            processed = process_publication_batch(db)
            if processed:
                logger.info('worker processed publications: %s', processed)
        finally:
            db.close()
        time.sleep(settings.worker_poll_interval_seconds)
