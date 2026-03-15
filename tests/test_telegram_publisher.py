from urllib import error

import pytest

from app.services.publish_errors import RetryablePublishError
from app.services.telegram_publisher import TelegramPublisher


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        import json
        return json.dumps(self.payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False



def _create_publication(client, with_username=True, draft_generation_metadata=None):
    project = client.post('/api/v1/projects', json={'name': 'Telegram Project', 'language': 'ru'}).json()
    channel_payload = {
        'channel_title': 'Telegram Channel',
        'publish_mode': 'manual',
        'is_active': True,
    }
    if with_username:
        channel_payload['channel_username'] = 'telegram_test_channel'
    channel = client.post(
        f"/api/v1/projects/{project['id']}/channels",
        json=channel_payload,
    ).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", json={'title': 'Telegram Task'}).json()
    draft = client.post(f"/api/v1/tasks/{task['id']}/drafts", json={'text': 'Telegram body', 'version': 1}).json()
    patch_payload = {'text': 'Telegram body'}
    if draft_generation_metadata is not None:
        patch_payload['generation_metadata'] = draft_generation_metadata
    draft = client.patch(
        f"/api/v1/drafts/{draft['id']}",
        json=patch_payload,
    ).json()
    client.post(f"/api/v1/drafts/{draft['id']}/approve")
    publication = client.post(
        f"/api/v1/drafts/{draft['id']}/publications",
        json={'telegram_channel_id': channel['id']},
    ).json()
    return task, publication



def test_telegram_publisher_interface_exists():
    publisher = TelegramPublisher()
    assert hasattr(publisher, 'publish')
    assert hasattr(publisher, 'fail')



def test_telegram_publisher_publish_success_updates_publication(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')
    monkeypatch.setattr(
        telegram_module.request,
        'urlopen',
        lambda req, timeout=20: DummyResponse({'ok': True, 'result': {'message_id': 12345}}),
    )

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'sent'
    assert result.external_message_id == '12345'

    task_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert task_res.json()['status'] == 'published'



def test_telegram_publisher_publish_without_token_marks_failed(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', None)

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'failed'
    assert result.error_message == 'TELEGRAM_BOT_TOKEN is not configured'



def test_telegram_publisher_publish_without_channel_target_marks_failed(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client, with_username=False)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'failed'
    assert 'channel_id or channel_username' in result.error_message



def test_telegram_publisher_http_error_marks_failed(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')

    class DummyHTTPError(error.HTTPError):
        def __init__(self):
            super().__init__('http://x', 400, 'Bad Request', hdrs=None, fp=None)

        def read(self):
            return b'{"ok":false,"description":"chat not found"}'

    monkeypatch.setattr(telegram_module.request, 'urlopen', lambda req, timeout=20: (_ for _ in ()).throw(DummyHTTPError()))

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'failed'
    assert 'Telegram HTTP 400' in result.error_message



def test_telegram_publisher_network_error_is_retryable(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')
    monkeypatch.setattr(
        telegram_module.request,
        'urlopen',
        lambda req, timeout=20: (_ for _ in ()).throw(error.URLError('timeout')),
    )

    with pytest.raises(RetryablePublishError) as exc:
        TelegramPublisher().publish(fake_db, publication['id'])

    assert 'Telegram network error' in str(exc.value)



def test_telegram_publisher_api_error_marks_failed(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')
    monkeypatch.setattr(
        telegram_module.request,
        'urlopen',
        lambda req, timeout=20: DummyResponse({'ok': False, 'description': 'bot was blocked by the user'}),
    )

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'failed'
    assert result.error_message == 'bot was blocked by the user'



def test_telegram_publisher_http_429_is_retryable_with_retry_after(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')

    class DummyTooManyRequests(error.HTTPError):
        def __init__(self):
            super().__init__('http://x', 429, 'Too Many Requests', hdrs=None, fp=None)

        def read(self):
            return b'{"ok":false,"description":"Too Many Requests: retry later","parameters":{"retry_after":3}}'

    monkeypatch.setattr(telegram_module.request, 'urlopen', lambda req, timeout=20: (_ for _ in ()).throw(DummyTooManyRequests()))

    with pytest.raises(RetryablePublishError) as exc:
        TelegramPublisher().publish(fake_db, publication['id'])

    assert 'Telegram HTTP 429' in str(exc.value)
    assert exc.value.retry_after_seconds == 3



def test_telegram_publisher_http_503_is_retryable(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(client)
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')

    class DummyServiceUnavailable(error.HTTPError):
        def __init__(self):
            super().__init__('http://x', 503, 'Service Unavailable', hdrs=None, fp=None)

        def read(self):
            return b'{"ok":false,"description":"service temporarily unavailable"}'

    monkeypatch.setattr(telegram_module.request, 'urlopen', lambda req, timeout=20: (_ for _ in ()).throw(DummyServiceUnavailable()))

    with pytest.raises(RetryablePublishError) as exc:
        TelegramPublisher().publish(fake_db, publication['id'])

    assert 'Telegram HTTP 503' in str(exc.value)



def test_telegram_publisher_publish_photo_success_updates_publication(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(
        client,
        draft_generation_metadata={'image_urls': ['https://example.com/image-1.jpg']},
    )
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')

    captured = {}

    def fake_urlopen(req, timeout=20):
        import json
        captured['url'] = req.full_url
        captured['payload'] = json.loads(req.data.decode('utf-8'))
        return DummyResponse({'ok': True, 'result': {'message_id': 98765}})

    monkeypatch.setattr(telegram_module.request, 'urlopen', fake_urlopen)

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'sent'
    assert result.external_message_id == '98765'
    assert captured['url'].endswith('/sendPhoto')
    assert captured['payload']['photo'] == 'https://example.com/image-1.jpg'
    assert captured['payload']['caption'] == 'Telegram body'



def test_telegram_publisher_publish_media_group_success_updates_publication(client, fake_db, monkeypatch):
    from app.services import telegram_publisher as telegram_module

    _task, publication = _create_publication(
        client,
        draft_generation_metadata={'image_urls': ['https://example.com/image-1.jpg', 'https://example.com/image-2.jpg']},
    )
    monkeypatch.setattr(telegram_module.settings, 'telegram_bot_token', 'token')

    captured = {}

    def fake_urlopen(req, timeout=20):
        import json
        captured['url'] = req.full_url
        captured['payload'] = json.loads(req.data.decode('utf-8'))
        return DummyResponse({'ok': True, 'result': [{'message_id': 222}, {'message_id': 223}]})

    monkeypatch.setattr(telegram_module.request, 'urlopen', fake_urlopen)

    result = TelegramPublisher().publish(fake_db, publication['id'])

    assert result.status.value == 'sent'
    assert result.external_message_id == '222'
    assert captured['url'].endswith('/sendMediaGroup')
    assert captured['payload']['media'][0]['type'] == 'photo'
    assert captured['payload']['media'][0]['caption'] == 'Telegram body'
    assert 'caption' not in captured['payload']['media'][1]



def test_telegram_publisher_fail_updates_publication(client, fake_db):
    _task, publication = _create_publication(client)

    result = TelegramPublisher().fail(fake_db, publication['id'], 'telegram error')

    assert result.status.value == 'failed'
    assert result.error_message == 'telegram error'
