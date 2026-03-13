from app.models.content_task import ContentTask
from app.utils.enums import ContentTaskStatus, PublicationStatus


def publication_status_on_create(is_scheduled: bool) -> PublicationStatus:
    return PublicationStatus.QUEUED if is_scheduled else PublicationStatus.SENDING



def task_status_on_publication_create(is_scheduled: bool) -> ContentTaskStatus:
    return ContentTaskStatus.SCHEDULED if is_scheduled else ContentTaskStatus.PUBLISHED



def sync_task_status_from_publication(task: ContentTask, publication_status: PublicationStatus) -> None:
    if publication_status == PublicationStatus.SENT:
        task.status = ContentTaskStatus.PUBLISHED
    elif publication_status == PublicationStatus.FAILED:
        task.status = ContentTaskStatus.FAILED
    elif publication_status == PublicationStatus.CANCELED:
        task.status = ContentTaskStatus.APPROVED
    elif publication_status == PublicationStatus.QUEUED:
        task.status = ContentTaskStatus.SCHEDULED
