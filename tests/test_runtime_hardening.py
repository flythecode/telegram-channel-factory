from app.services.publish_errors import RetryablePublishError
from app.services.runtime_hardening import dispatch_publication_with_retry, mark_publication_failed_after_runtime_error


class _FailOnce:
    def __init__(self):
        self.calls = 0

    def __call__(self, db, publication_id):
        self.calls += 1
        if self.calls == 1:
            raise RetryablePublishError('temporary failure')
        return 'ok'


def test_dispatch_publication_with_retry_retries_once(monkeypatch, fake_db):
    fail_once = _FailOnce()
    monkeypatch.setattr('app.services.runtime_hardening.dispatch_publication', fail_once)

    result = dispatch_publication_with_retry(fake_db, 'pub-1', retries=1, backoff_seconds=0)

    assert result == 'ok'
    assert fail_once.calls == 2



def test_dispatch_publication_with_retry_does_not_retry_non_retryable_errors(monkeypatch, fake_db):
    class _FailHard:
        def __init__(self):
            self.calls = 0

        def __call__(self, db, publication_id):
            self.calls += 1
            raise RuntimeError('hard failure')

    fail_hard = _FailHard()
    monkeypatch.setattr('app.services.runtime_hardening.dispatch_publication', fail_hard)

    try:
        dispatch_publication_with_retry(fake_db, 'pub-hard', retries=3, backoff_seconds=0)
    except RuntimeError as exc:
        assert str(exc) == 'hard failure'
    else:  # pragma: no cover
        raise AssertionError('Expected RuntimeError')

    assert fail_hard.calls == 1


class _DummyPublisher:
    def __init__(self):
        self.calls = []

    def fail(self, db, publication_id, reason='publisher failure'):
        self.calls.append((publication_id, reason))
        return {'publication_id': publication_id, 'reason': reason}



def test_mark_publication_failed_after_runtime_error_uses_publisher_fail(monkeypatch, fake_db):
    publisher = _DummyPublisher()
    monkeypatch.setattr('app.services.runtime_hardening.get_publisher', lambda: publisher)

    result = mark_publication_failed_after_runtime_error(fake_db, 'pub-2', RuntimeError('boom'))

    assert publisher.calls == [('pub-2', 'Worker runtime error: boom')]
    assert result['publication_id'] == 'pub-2'
