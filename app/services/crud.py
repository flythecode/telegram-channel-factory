from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.audit_service import maybe_audit_create, maybe_audit_update, snapshot_entity



def create_entity(db: Session, model_cls: type, payload: Any, **extra_fields):
    entity = model_cls(**payload.model_dump(), **extra_fields)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    maybe_audit_create(db, entity)
    return entity



def get_entity_or_404(db: Session, model_cls: type, entity_id: Any, detail: str):
    entity = db.get(model_cls, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=detail)
    return entity



def update_entity(db: Session, entity: Any, payload: Any):
    before = snapshot_entity(entity)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    maybe_audit_update(db, entity, before)
    return entity
