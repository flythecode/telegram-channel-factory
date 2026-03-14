import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.services.runtime_hardening import (
    dispatch_publication_with_retry,
    mark_publication_failed_after_runtime_error,
)
from app.utils.enums import PublicationStatus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkerBatchSummary:
    seen: int
    dispatchable: int
    processed: int
    failed: int
    started_at: str
    finished_at: str
    duration_ms: float

    def to_dict(self) -> dict:
        return asdict(self)



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
    return process_publication_batch_with_summary(db).processed



def process_publication_batch_with_summary(db: Session) -> WorkerBatchSummary:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    dispatchable_items = collect_dispatchable_publications(db)
    processed = 0
    failed = 0
    for publication in dispatchable_items:
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
    finished_at = datetime.now(timezone.utc)
    summary = WorkerBatchSummary(
        seen=len(db.query(Publication).all()),
        dispatchable=len(dispatchable_items),
        processed=processed,
        failed=failed,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=round((perf_counter() - started_perf) * 1000, 2),
    )
    logger.info("worker batch complete", extra=summary.to_dict())
    return summary
