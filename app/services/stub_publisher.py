import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.publication import Publication
from app.services.crud import get_entity_or_404
from app.services.publications import sync_task_status_from_publication
from app.services.publisher_interface import PublisherInterface
from app.utils.enums import PublicationStatus

logger = logging.getLogger(__name__)


class StubPublisher(PublisherInterface):
    def publish(self, db: Session, publication_id):
        publication = get_entity_or_404(db, Publication, publication_id, "Publication not found")

        publication.status = PublicationStatus.SENT
        publication.published_at = datetime.now(timezone.utc)
        publication.external_message_id = f"stub-{uuid4().hex[:12]}"
        publication.error_message = None

        task = publication.draft.content_task
        sync_task_status_from_publication(task, publication.status)

        db.add(publication)
        db.add(task)
        db.commit()
        db.refresh(publication)
        logger.info(
            "stub publication sent",
            extra={
                "publication_id": str(publication.id),
                "message_id": publication.external_message_id,
                "task_id": str(task.id),
            },
        )
        return publication

    def fail(self, db: Session, publication_id, reason: str = "stub failure"):
        publication = get_entity_or_404(db, Publication, publication_id, "Publication not found")

        publication.status = PublicationStatus.FAILED
        publication.error_message = reason

        task = publication.draft.content_task
        sync_task_status_from_publication(task, publication.status)

        db.add(publication)
        db.add(task)
        db.commit()
        db.refresh(publication)
        logger.warning(
            "stub publication failed",
            extra={
                "publication_id": str(publication.id),
                "task_id": str(task.id),
                "reason": reason,
            },
        )
        return publication


stub_publisher = StubPublisher()
