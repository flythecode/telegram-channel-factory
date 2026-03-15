import logging

from sqlalchemy.orm import Session

from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.publication import Publication
from app.models.telegram_channel import TelegramChannel
from app.schemas.publication import PublicationCreate, PublicationUpdate
from app.services.crud import get_entity_or_404, update_entity
from app.services.publisher_factory import get_publisher
from app.services.generation_metadata import build_publication_generation_metadata
from app.services.publications import (
    publication_status_on_create,
    sync_task_status_from_publication,
    task_status_on_publication_create,
)
from app.utils.enums import DraftStatus, PublicationStatus

logger = logging.getLogger(__name__)


ACTIVE_PUBLICATION_STATUSES = {
    PublicationStatus.QUEUED,
    PublicationStatus.SENDING,
    PublicationStatus.SENT,
}


def _list_publications_for_draft(db: Session, draft_id) -> list[Publication]:
    rows = db.query(Publication).all()
    return [publication for publication in rows if str(publication.draft_id) == str(draft_id)]


def _find_existing_publication(db: Session, draft_id, channel_id) -> Publication | None:
    matches = [
        publication
        for publication in _list_publications_for_draft(db, draft_id)
        if str(publication.telegram_channel_id) == str(channel_id)
        and publication.status in ACTIVE_PUBLICATION_STATUSES
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (getattr(item, 'created_at', None), str(item.id)), reverse=True)
    return matches[0]


def queue_publication(db: Session, draft_id, payload: PublicationCreate) -> Publication:
    draft = get_entity_or_404(db, Draft, draft_id, "Draft not found")
    get_entity_or_404(db, TelegramChannel, payload.telegram_channel_id, "Channel not found")

    if draft.status != DraftStatus.APPROVED:
        raise ValueError("Only approved drafts can be queued for publication")

    existing = _find_existing_publication(db, draft_id, payload.telegram_channel_id)
    if existing is not None:
        logger.info(
            "publication duplicate prevented",
            extra={
                "publication_id": str(existing.id),
                "draft_id": str(draft_id),
                "channel_id": str(payload.telegram_channel_id),
                "publication_status": existing.status.value,
            },
        )
        return existing

    is_scheduled = payload.scheduled_for is not None
    publication = Publication(
        draft_id=draft_id,
        telegram_channel_id=payload.telegram_channel_id,
        scheduled_for=payload.scheduled_for,
        status=publication_status_on_create(is_scheduled),
        generation_metadata=build_publication_generation_metadata(draft, telegram_channel_id=payload.telegram_channel_id),
    )
    db.add(publication)

    task: ContentTask = draft.content_task
    task.status = task_status_on_publication_create(is_scheduled)
    db.add(task)

    db.commit()
    db.refresh(publication)
    logger.info(
        "publication queued",
        extra={
            "publication_id": str(publication.id),
            "draft_id": str(draft_id),
            "channel_id": str(payload.telegram_channel_id),
            "scheduled": is_scheduled,
            "publication_status": publication.status.value,
            "task_status": task.status.value,
        },
    )
    return publication



def update_publication_state(db: Session, publication_id, payload: PublicationUpdate) -> Publication:
    publication = get_entity_or_404(db, Publication, publication_id, "Publication not found")
    current_status = publication.status
    target_status = payload.status if payload.status is not None else current_status
    if current_status == target_status:
        if payload.scheduled_for is None or publication.scheduled_for == payload.scheduled_for:
            return publication
    publication = update_entity(db, publication, payload)

    task: ContentTask = publication.draft.content_task
    sync_task_status_from_publication(task, publication.status)

    db.add(publication)
    db.add(task)
    db.commit()
    db.refresh(publication)
    logger.info(
        "publication state updated",
        extra={
            "publication_id": str(publication.id),
            "publication_status": publication.status.value,
            "task_id": str(task.id),
            "task_status": task.status.value,
        },
    )
    return publication



def dispatch_publication(db: Session, publication_id) -> Publication:
    publisher = get_publisher()
    logger.info(
        "dispatching publication",
        extra={
            "publication_id": str(publication_id),
            "publisher": type(publisher).__name__,
        },
    )
    return publisher.publish(db, publication_id)
