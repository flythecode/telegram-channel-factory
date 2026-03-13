from __future__ import annotations

from datetime import datetime, timezone

from app.utils.enums import DraftStatus, PublicationStatus


MODE_ALIASES = {
    'manual': 'manual',
    'semi_auto': 'semi_auto',
    'scheduled': 'semi_auto',
    'auto': 'auto',
}

MODE_TO_BACKEND = {
    'manual': 'manual',
    'semi_auto': 'scheduled',
    'scheduled': 'scheduled',
    'auto': 'auto',
}


DRAFT_STATUS_LABELS = {
    DraftStatus.CREATED.value: 'Новый черновик',
    DraftStatus.EDITED.value: 'Изменён, ждёт решения',
    DraftStatus.APPROVED.value: 'Подтверждён',
    DraftStatus.REJECTED.value: 'Отклонён',
    DraftStatus.PUBLISHED.value: 'Опубликован',
}

PUBLICATION_STATUS_LABELS = {
    PublicationStatus.QUEUED.value: 'В очереди',
    PublicationStatus.SENDING.value: 'Отправляется',
    PublicationStatus.SENT.value: 'Отправлено',
    PublicationStatus.FAILED.value: 'Ошибка отправки',
    PublicationStatus.CANCELED.value: 'Отменено',
}

ACTION_LABELS = {
    'approve': 'Черновик подтверждён',
    'reject': 'Черновик отклонён',
    'regenerate': 'Черновик пересобран',
    'edit': 'Черновик обновлён',
    'create_publication': 'Публикация создана',
    'publish_now': 'Публикация отправлена в немедленную отправку',
    'cancel_publication': 'Публикация отменена',
    'schedule_publication': 'Время публикации обновлено',
}


def human_mode_label(mode: str) -> str:
    normalized = MODE_ALIASES.get(mode, mode)
    return {
        'manual': 'manual — каждое важное действие подтверждаешь ты',
        'semi_auto': 'semi_auto — бот ведёт очередь и расписание, но ключевые решения остаются за тобой',
        'auto': 'auto — максимум автоматизации без ручного подтверждения каждого шага',
    }.get(normalized, normalized)



def human_draft_status(status: str) -> str:
    return DRAFT_STATUS_LABELS.get(status, status)



def human_publication_status(status: str) -> str:
    return PUBLICATION_STATUS_LABELS.get(status, status)



def human_action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)



def classify_publication_error(error_message: str | None) -> str | None:
    if not error_message:
        return None
    lowered = error_message.lower()
    temporary_markers = (
        'too many requests',
        'retry later',
        'timeout',
        'timed out',
        'network error',
        'temporary',
        'http 429',
        'http 500',
        'http 502',
        'http 503',
        'http 504',
    )
    if any(marker in lowered for marker in temporary_markers):
        return 'temporary'
    return 'terminal'



def human_publication_error(error_message: str | None) -> str:
    if not error_message:
        return '—'
    classification = classify_publication_error(error_message)
    if classification == 'temporary':
        return (
            'Временная ошибка Telegram/сети. '
            f'Техническая причина: {error_message}. '
            'Что делать: подождать и повторить публикацию позже.'
        )
    return (
        'Похоже на постоянную ошибку публикации. '
        f'Техническая причина: {error_message}. '
        'Что проверить: права бота, target канала и настройки подключения.'
    )



def format_schedule(schedule: str | None) -> str:
    if not schedule:
        return 'Сразу'
    try:
        dt = datetime.fromisoformat(schedule.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except ValueError:
        return schedule



def parse_user_schedule(raw: str) -> datetime | None:
    text = raw.strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M UTC'):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
