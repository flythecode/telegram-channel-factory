from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session



def create_entity(db: Session, model_cls: type, payload: Any, **extra_fields):
    entity = model_cls(**payload.model_dump(), **extra_fields)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity



def get_entity_or_404(db: Session, model_cls: type, entity_id: Any, detail: str):
    entity = db.get(model_cls, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=detail)
    return entity



def update_entity(db: Session, entity: Any, payload: Any):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity
