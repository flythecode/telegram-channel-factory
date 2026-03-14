import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.worker import WorkerBatchSummary, process_publication_batch_with_summary



def test_process_publication_batch_with_summary_reports_counts(client, fake_db):
    project = client.post('/api/v1/projects', json={'name': 'Monitoring Project', 'language': 'ru'}).json()
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json={
            'channel_title': 'Monitoring Channel',
            'channel_id': f"monitor-{datetime.now(timezone.utc).timestamp()}",
            'publish_mode': 'manual',
            'is_active': True,
        },
    ).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Monitoring Task'}).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Monitoring draft', 'version': 1}).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")
    client.post(f"/api/v1/drafts/{draft['id']}/publications", json={'telegram_channel_id': channel['id']})

    summary = process_publication_batch_with_summary(fake_db)

    assert isinstance(summary, WorkerBatchSummary)
    assert summary.seen >= 1
    assert summary.dispatchable >= 1
    assert summary.processed == 1
    assert summary.failed == 0
    assert summary.duration_ms >= 0



def test_check_worker_status_returns_ok_for_fresh_running_state(tmp_path):
    from scripts import check_worker_status as module

    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path = runtime_dir / 'worker_status.json'
    state_path.write_text(
        json.dumps(
            {
                'status': 'running',
                'last_heartbeat_at': datetime.now(timezone.utc).isoformat(),
                'last_error': None,
                'last_summary': {'processed': 2, 'failed': 0},
            }
        ),
        encoding='utf-8',
    )

    module.STATE_PATH = state_path
    assert module.main() == 0



def test_check_worker_status_fails_for_stale_heartbeat(tmp_path):
    from scripts import check_worker_status as module

    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path = runtime_dir / 'worker_status.json'
    state_path.write_text(
        json.dumps(
            {
                'status': 'running',
                'last_heartbeat_at': (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                'last_error': None,
                'last_summary': {'processed': 0, 'failed': 0},
            }
        ),
        encoding='utf-8',
    )

    module.STATE_PATH = state_path
    assert module.main() == 1



def test_check_worker_status_fails_for_degraded_state(tmp_path):
    from scripts import check_worker_status as module

    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state_path = runtime_dir / 'worker_status.json'
    state_path.write_text(
        json.dumps(
            {
                'status': 'degraded',
                'last_heartbeat_at': datetime.now(timezone.utc).isoformat(),
                'last_error': 'db unavailable',
                'last_summary': {'processed': 0, 'failed': 1},
            }
        ),
        encoding='utf-8',
    )

    module.STATE_PATH = state_path
    assert module.main() == 1
