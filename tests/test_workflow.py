from types import SimpleNamespace

from app.services.publications import (
    publication_status_on_create,
    sync_task_status_from_publication,
    task_status_on_publication_create,
)
from app.services.workflow import approve_draft, mark_task_as_drafted, reject_draft
from app.utils.enums import ContentTaskStatus, DraftStatus, PublicationStatus



def test_mark_task_as_drafted_updates_both_entities():
    task = SimpleNamespace(status=ContentTaskStatus.PENDING)
    draft = SimpleNamespace(status=None)

    mark_task_as_drafted(task, draft)

    assert draft.status == DraftStatus.CREATED
    assert task.status == ContentTaskStatus.DRAFTED



def test_approve_draft_updates_both_entities():
    task = SimpleNamespace(status=ContentTaskStatus.DRAFTED)
    draft = SimpleNamespace(status=DraftStatus.CREATED)

    approve_draft(task, draft)

    assert draft.status == DraftStatus.APPROVED
    assert task.status == ContentTaskStatus.APPROVED



def test_reject_draft_updates_both_entities():
    task = SimpleNamespace(status=ContentTaskStatus.DRAFTED)
    draft = SimpleNamespace(status=DraftStatus.CREATED)

    reject_draft(task, draft)

    assert draft.status == DraftStatus.REJECTED
    assert task.status == ContentTaskStatus.REJECTED



def test_publication_status_on_create_for_scheduled_publication():
    assert publication_status_on_create(True) == PublicationStatus.QUEUED
    assert task_status_on_publication_create(True) == ContentTaskStatus.SCHEDULED



def test_publication_status_on_create_for_immediate_publication():
    assert publication_status_on_create(False) == PublicationStatus.SENDING
    assert task_status_on_publication_create(False) == ContentTaskStatus.PUBLISHED



def test_sync_task_status_from_publication_sent():
    task = SimpleNamespace(status=ContentTaskStatus.APPROVED)

    sync_task_status_from_publication(task, PublicationStatus.SENT)

    assert task.status == ContentTaskStatus.PUBLISHED



def test_sync_task_status_from_publication_failed():
    task = SimpleNamespace(status=ContentTaskStatus.APPROVED)

    sync_task_status_from_publication(task, PublicationStatus.FAILED)

    assert task.status == ContentTaskStatus.FAILED



def test_sync_task_status_from_publication_canceled():
    task = SimpleNamespace(status=ContentTaskStatus.SCHEDULED)

    sync_task_status_from_publication(task, PublicationStatus.CANCELED)

    assert task.status == ContentTaskStatus.APPROVED



def test_sync_task_status_from_publication_queued():
    task = SimpleNamespace(status=ContentTaskStatus.APPROVED)

    sync_task_status_from_publication(task, PublicationStatus.QUEUED)

    assert task.status == ContentTaskStatus.SCHEDULED
