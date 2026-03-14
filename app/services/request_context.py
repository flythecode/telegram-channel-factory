from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar('request_id', default=None)
_telegram_user_id: ContextVar[str | None] = ContextVar('telegram_user_id', default=None)


def set_request_context(*, request_id: str | None, telegram_user_id: str | None):
    request_token = _request_id.set(request_id)
    telegram_token = _telegram_user_id.set(telegram_user_id)
    return request_token, telegram_token


def reset_request_context(request_token, telegram_token):
    _request_id.reset(request_token)
    _telegram_user_id.reset(telegram_token)


def get_request_id() -> str | None:
    return _request_id.get()


def get_telegram_user_id() -> str | None:
    return _telegram_user_id.get()
