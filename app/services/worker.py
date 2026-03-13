import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.services.runtime_hardening import (
    dispatch_publication_with_retry,
    mark_publication_failed_after_runtime_error,
)
from app.utils.enums import PublicationStatus

logger = logging.getLogger(__name__)



def collect_dispatchable_publications(db: Session) -> list[Publication]:
    now = datetime.now(timezone.utc)
    items = db.query(Publication).all()
    dispatchable = []
    for publication in items:
        if publication.status == PublicationStatus.SENDING:
            dispatchable.append(publication)
        elif publication.status == PublicationStatus.QUEUED:
            if publication.scheduled_for is None or publication.scheduled_for <= now:
                dispatchable.append(publication)
    logger.info(
        "worker collected publications",
        extra={
            "seen": len(items),
            "dispatchable": len(dispatchable),
        },
    )
    return dispatchable



def process_publication_batch(db: Session) -> int:
    processed = 0
    failed = 0
    for publication in collect_dispatchable_publications(db):
        logger.info(
            "worker processing publication",
            extra={
                "publication_id": str(publication.id),
                "status": publication.status.value,
            },
        )
        try:
            dispatch_publication_with_retry(db, publication.id)
            processed += 1
        except Exception as exc:  # pragma: no cover - defensive wrapper
            failed += 1
            mark_publication_failed_after_runtime_error(db, publication.id, exc)
            logger.exception(
                "worker publication failed after retries",
                extra={
                    "publication_id": str(publication.id),
                    "error": str(exc),
                },
            )
    logger.info("worker batch complete", extra={"processed": processed, "failed": failed})
    return processed
