from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.user import UserRead
from app.schemas.workspace import WorkspaceRead
from app.services.identity import (
    TelegramIdentity,
    get_or_create_current_user,
    get_or_create_workspace_for_user,
    get_telegram_identity,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_current_user(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    return get_or_create_current_user(db, identity)


@router.get("/me/workspace", response_model=WorkspaceRead)
def get_my_workspace(
    identity: TelegramIdentity = Depends(get_telegram_identity),
    db: Session = Depends(get_db),
):
    user = get_or_create_current_user(db, identity)
    return get_or_create_workspace_for_user(db, user, identity)
