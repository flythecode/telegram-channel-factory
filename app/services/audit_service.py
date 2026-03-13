from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent



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
        notes=notes,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event



def list_audit_events_for_project(db: Session, project_id):
    items = [event for event in db.query(AuditEvent).all() if event.project_id == project_id]
    items.sort(key=lambda item: item.created_at)
    return items
