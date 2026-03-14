import re
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.services.request_context import get_request_id, get_telegram_user_id


ACTION_LABELS = {
    'create_project': 'создан проект',
    'update_project_settings': 'обновлены настройки проекта',
    'create_content_plan': 'создан контент-план',
    'update_content_plan': 'обновлён контент-план',
    'create_task': 'создана задача',
    'update_task': 'обновлена задача',
    'create_channel': 'создан канал',
    'update_channel': 'обновлён канал',
    'connect_channel': 'обновлено подключение канала',
    'create_draft': 'создан черновик',
    'update_draft': 'обновлён черновик',
    'approve_draft': 'черновик подтверждён',
    'reject_draft': 'черновик отклонён',
    'regenerate_draft': 'черновик перегенерирован',
    'create_publication': 'создана публикация',
    'update_publication': 'обновлена публикация',
    'publish_now': 'запущена немедленная публикация',
    'cancel_publication': 'публикация отменена',
    'update_agent': 'обновлён агент',
    'enable_agent': 'агент включён',
    'disable_agent': 'агент выключен',
    'update_agent_prompts': 'обновлены промпты агента',
}


CTX_REQUEST_RE = re.compile(r'request_id=([^;]+)')
CTX_TELEGRAM_RE = re.compile(r'telegram_user_id=([^;]+)')


AUDIT_ACTIONS = {
    'Project': {'create': 'create_project'},
    'ContentPlan': {'create': 'create_content_plan', 'update': 'update_content_plan'},
    'ContentTask': {'create': 'create_task', 'update': 'update_task'},
    'TelegramChannel': {'create': 'create_channel', 'update': 'update_channel'},
    'Draft': {'update': 'update_draft'},
}


ENTITY_TYPES = {
    'Project': 'project',
    'ContentPlan': 'content_plan',
    'ContentTask': 'task',
    'TelegramChannel': 'channel',
    'Draft': 'draft',
}


SUMMARY_FIELDS = ('name', 'channel_title', 'channel_username', 'title', 'status', 'operation_mode')


def _normalize(value):
    if hasattr(value, 'value'):
        return value.value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if value is not None and not isinstance(value, (str, int, float, bool, dict, list)):
        return str(value)
    return value


def snapshot_entity(entity, fields: list[str] | None = None) -> dict:
    field_names = fields or [column.key for column in entity.__table__.columns]
    return {field: _normalize(getattr(entity, field, None)) for field in field_names}


def _merge_notes_with_context(notes: str | None) -> str | None:
    parts = []
    if notes:
        parts.append(notes)
    request_id = get_request_id()
    telegram_user_id = get_telegram_user_id()
    if request_id:
        parts.append(f'request_id={request_id}')
    if telegram_user_id:
        parts.append(f'telegram_user_id={telegram_user_id}')
    return '; '.join(parts) if parts else None


def create_audit_event(
    db: Session,
    *,
    project_id=None,
    user_id=None,
    entity_type: str,
    entity_id=None,
    action: str,
    before_json=None,
    after_json=None,
    notes: str | None = None,
):
    event = AuditEvent(
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_json=before_json,
        after_json=after_json,
        notes=_merge_notes_with_context(notes),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _extract_changed_fields(before_json: dict | None, after_json: dict | None) -> list[str]:
    keys: Iterable[str] = set((before_json or {}).keys()) | set((after_json or {}).keys())
    return sorted([key for key in keys if (before_json or {}).get(key) != (after_json or {}).get(key)])


def _extract_context_value(pattern: re.Pattern[str], notes: str | None) -> str | None:
    if not notes:
        return None
    match = pattern.search(notes)
    return match.group(1).strip() if match else None


def _build_summary(event: AuditEvent, changed_fields: list[str]) -> str:
    label = ACTION_LABELS.get(event.action, event.action.replace('_', ' '))
    focus = None
    data = event.after_json or event.before_json or {}
    for field in SUMMARY_FIELDS:
        if data.get(field):
            focus = f'{field}={data[field]}'
            break
    if changed_fields:
        diff = ', '.join(changed_fields[:5])
        if len(changed_fields) > 5:
            diff += ', ...'
        label = f'{label}; изменения: {diff}'
    if focus:
        return f'{label}; {focus}'
    return label


def serialize_audit_event(event: AuditEvent) -> dict:
    before_json = event.before_json or None
    after_json = event.after_json or None
    changed_fields = _extract_changed_fields(before_json, after_json)
    request_id = _extract_context_value(CTX_REQUEST_RE, event.notes)
    actor = _extract_context_value(CTX_TELEGRAM_RE, event.notes)
    return {
        'id': event.id,
        'created_at': event.created_at,
        'updated_at': event.updated_at,
        'project_id': event.project_id,
        'user_id': event.user_id,
        'entity_type': event.entity_type,
        'entity_id': event.entity_id,
        'action': event.action,
        'before_json': before_json,
        'after_json': after_json,
        'notes': event.notes,
        'changed_fields': changed_fields,
        'summary': _build_summary(event, changed_fields),
        'request_id': request_id,
        'actor': actor,
    }


def list_audit_events_for_project(db: Session, project_id, *, action: str | None = None, entity_type: str | None = None, limit: int = 100):
    items = [event for event in db.query(AuditEvent).all() if event.project_id == project_id]
    if action:
        items = [event for event in items if event.action == action]
    if entity_type:
        items = [event for event in items if event.entity_type == entity_type]
    items.sort(key=lambda item: (item.created_at, str(item.id)), reverse=True)
    return [serialize_audit_event(event) for event in items[:limit]]


def _resolve_project_id(entity) -> object | None:
    if hasattr(entity, 'project_id'):
        return getattr(entity, 'project_id')
    if entity.__class__.__name__ == 'Project':
        return getattr(entity, 'id', None)
    if entity.__class__.__name__ == 'Draft' and getattr(entity, 'content_task', None) is not None:
        return getattr(entity.content_task, 'project_id', None)
    if entity.__class__.__name__ == 'Publication' and getattr(entity, 'draft', None) is not None:
        task = getattr(entity.draft, 'content_task', None)
        return getattr(task, 'project_id', None) if task is not None else None
    return None


def maybe_audit_create(db: Session, entity, *, notes: str | None = None):
    config = AUDIT_ACTIONS.get(entity.__class__.__name__)
    if not config or 'create' not in config:
        return None
    return create_audit_event(
        db,
        project_id=_resolve_project_id(entity),
        entity_type=ENTITY_TYPES[entity.__class__.__name__],
        entity_id=getattr(entity, 'id', None),
        action=config['create'],
        before_json=None,
        after_json=snapshot_entity(entity),
        notes=notes,
    )


def maybe_audit_update(db: Session, entity, before_json: dict | None, *, notes: str | None = None):
    config = AUDIT_ACTIONS.get(entity.__class__.__name__)
    if not config or 'update' not in config:
        return None
    after_json = snapshot_entity(entity)
    if before_json == after_json:
        return None
    return create_audit_event(
        db,
        project_id=_resolve_project_id(entity),
        entity_type=ENTITY_TYPES[entity.__class__.__name__],
        entity_id=getattr(entity, 'id', None),
        action=config['update'],
        before_json=before_json,
        after_json=after_json,
        notes=notes,
    )
