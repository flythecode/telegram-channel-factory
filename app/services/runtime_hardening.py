import logging
import time

from sqlalchemy.orm import Session

from app.services.publish_errors import RetryablePublishError
from app.services.publish_service import dispatch_publication
from app.services.publisher_factory import get_publisher

logger = logging.getLogger(__name__)



def dispatch_publication_with_retry(db: Session, publication_id, retries: int = 2, backoff_seconds: float = 0.01):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return dispatch_publication(db, publication_id)
        except RetryablePublishError as exc:
            last_error = exc
            logger.warning(
                'publication dispatch attempt failed',
                extra={
                    'publication_id': str(publication_id),
                    'attempt': attempt + 1,
                    'retries': retries,
                    'error': str(exc),
                    'retryable': True,
                    'retry_after_seconds': exc.retry_after_seconds,
                },
            )
            if attempt == retries:
                raise
            sleep_seconds = exc.retry_after_seconds if exc.retry_after_seconds is not None else backoff_seconds * (attempt + 1)
            time.sleep(max(sleep_seconds, 0))
        except Exception as exc:  # pragma: no cover - defensive wrapper
            last_error = exc
            logger.warning(
                'publication dispatch attempt failed',
                extra={
                    'publication_id': str(publication_id),
                    'attempt': attempt + 1,
                    'retries': retries,
                    'error': str(exc),
                    'retryable': False,
                },
            )
            raise
    raise last_error



def mark_publication_failed_after_runtime_error(db: Session, publication_id, exc: Exception):
    publisher = get_publisher()
    return publisher.fail(db, publication_id, f'Worker runtime error: {exc}')
