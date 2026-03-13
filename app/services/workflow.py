from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.utils.enums import ContentTaskStatus, DraftStatus


def mark_task_as_drafted(task: ContentTask, draft: Draft) -> None:
    draft.status = DraftStatus.CREATED
    task.status = ContentTaskStatus.DRAFTED


def approve_draft(task: ContentTask, draft: Draft) -> None:
    draft.status = DraftStatus.APPROVED
    task.status = ContentTaskStatus.APPROVED


def reject_draft(task: ContentTask, draft: Draft) -> None:
    draft.status = DraftStatus.REJECTED
    task.status = ContentTaskStatus.REJECTED
