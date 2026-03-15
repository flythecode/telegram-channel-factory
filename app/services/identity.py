from dataclasses import dataclass
from uuid import uuid4

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.models.client_account import ClientAccount
from app.models.user import User
from app.models.workspace import Workspace


@dataclass(slots=True)
class TelegramIdentity:
    telegram_user_id: str
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None



def get_telegram_identity(
    x_telegram_user_id: str | None = Header(default=None),
    x_telegram_username: str | None = Header(default=None),
    x_telegram_first_name: str | None = Header(default=None),
    x_telegram_last_name: str | None = Header(default=None),
) -> TelegramIdentity:
    if not x_telegram_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram identity context",
        )
    return TelegramIdentity(
        telegram_user_id=x_telegram_user_id,
        telegram_username=x_telegram_username,
        first_name=x_telegram_first_name,
        last_name=x_telegram_last_name,
    )



def _workspace_slug(identity: TelegramIdentity) -> str:
    base = identity.telegram_username or f"tg-{identity.telegram_user_id}"
    return f"workspace-{base}".lower().replace(" ", "-")



def get_or_create_current_user(db: Session, identity: TelegramIdentity) -> User:
    for user in db.query(User).all():
        if user.telegram_user_id == identity.telegram_user_id:
            if identity.telegram_username and not user.full_name:
                user.full_name = identity.telegram_username
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    full_name = " ".join(part for part in [identity.first_name, identity.last_name] if part).strip() or identity.telegram_username
    email = f"tg-{identity.telegram_user_id}@telegram.local"
    user = User(
        email=email,
        full_name=full_name or None,
        telegram_user_id=identity.telegram_user_id,
        preferences={"telegram_username": identity.telegram_username} if identity.telegram_username else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



def get_or_create_workspace_for_user(db: Session, user: User, identity: TelegramIdentity) -> Workspace:
    for workspace in db.query(Workspace).all():
        if workspace.owner_user_id == user.id:
            return workspace

    workspace = Workspace(
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name=(user.full_name or f"Telegram User {identity.telegram_user_id}") + " Workspace",
        slug=_workspace_slug(identity) + "-" + str(uuid4())[:8],
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace



def get_or_create_client_account_for_user(db: Session, user: User, workspace: Workspace, identity: TelegramIdentity) -> ClientAccount:
    for account in db.query(ClientAccount).all():
        if account.owner_user_id == user.id and (account.workspace_id is None or account.workspace_id == workspace.id):
            if workspace.id and account.workspace_id is None:
                account.workspace_id = workspace.id
                db.add(account)
                db.commit()
                db.refresh(account)
            return account

    account_name = user.full_name or identity.telegram_username or f"Telegram User {identity.telegram_user_id}"
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name=account_name,
        billing_email=user.email,
        subscription_plan_code="trial",
        subscription_status="trial",
        settings={"source": "telegram_identity", "telegram_user_id": identity.telegram_user_id, "generation_mode": "multi-stage"},
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account
