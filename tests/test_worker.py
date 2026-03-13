from datetime import datetime, timedelta, timezone

from app.models.publication import Publication
from app.utils.enums import ContentTaskStatus, PublicationStatus
from app.services.worker import collect_dispatchable_publications, process_publication_batch



def _create_publication(client, scheduled_for=None):
    project = client.post('/api/v1/projects', json={'name': 'Worker Project', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Worker Channel',
            'channel_id': f"worker-{datetime.now(timezone.utc).timestamp()}",
            'publish_mode': 'manual',
            'is_active': True,
        },
    ).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Worker Task'}).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Worker draft', 'version': 1}).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")
    payload = {'telegram_channel_id': channel['id']}
    if scheduled_for:
        payload['scheduled_for'] = scheduled_for
    publication = client.post(f"/api/v1/drafts/{draft['id']}/publications", json=payload).json()
    return task, publication



def test_collect_dispatchable_publications_returns_immediate_and_due_scheduled(client, fake_db):
    _create_publication(client)
    _create_publication(client, (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace('+00:00', 'Z'))
    _create_publication(client, (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'))

    items = collect_dispatchable_publications(fake_db)
    ids = {str(item.id) for item in items}

    assert len(ids) == 2



def test_process_publication_batch_dispatches_ready_publications(client, fake_db):
    task, publication = _create_publication(client)

    processed = process_publication_batch(fake_db)

    assert processed == 1
    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.status_code == 200
    assert task_res.json()['status'] == 'published'

    get_publication = client.get(f"/api/v1/publications/{publication['id']}")
    assert get_publication.status_code == 200
    assert get_publication.json()['status'] == 'sent'



def test_process_publication_batch_continues_after_runtime_failure(client, fake_db, monkeypatch):
    _failed_task, failed_publication = _create_publication(client)
    ok_task, ok_publication = _create_publication(client)

    def _fake_dispatch_with_retry(db, publication_id):
        if str(publication_id) == failed_publication['id']:
            raise RuntimeError('unexpected crash')
        publication = db.get(Publication, publication_id)
        publication.status = PublicationStatus.SENT
        publication.error_message = None
        task = publication.draft.content_task
        task.status = ContentTaskStatus.PUBLISHED
        db.add(publication)
        db.add(task)
        db.commit()
        db.refresh(publication)
        return publication

    def _fake_mark_failed(db, publication_id, exc):
        publication = db.get(Publication, publication_id)
        publication.status = PublicationStatus.FAILED
        publication.error_message = f'Worker runtime error: {exc}'
        task = publication.draft.content_task
        task.status = ContentTaskStatus.FAILED
        db.add(publication)
        db.add(task)
        db.commit()
        db.refresh(publication)
        return publication

    monkeypatch.setattr('app.services.worker.dispatch_publication_with_retry', _fake_dispatch_with_retry)
    monkeypatch.setattr('app.services.worker.mark_publication_failed_after_runtime_error', _fake_mark_failed)

    processed = process_publication_batch(fake_db)

    assert processed == 1

    failed_publication_res = client.get(f"/api/v1/publications/{failed_publication['id']}")
    assert failed_publication_res.status_code == 200
    assert failed_publication_res.json()['status'] == 'failed'
    assert failed_publication_res.json()['error_message'] == 'Worker runtime error: unexpected crash'

    ok_publication_res = client.get(f"/api/v1/publications/{ok_publication['id']}")
    assert ok_publication_res.status_code == 200
    assert ok_publication_res.json()['status'] == 'sent'

    ok_task_res = client.get(f"/api/v1/tasks/{ok_task['id']}")
    assert ok_task_res.status_code == 200
    assert ok_task_res.json()['status'] == 'published'
