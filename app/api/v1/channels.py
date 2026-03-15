from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.schemas.channel import TelegramChannelCreate, TelegramChannelRead, TelegramChannelUpdate
from app.schemas.channel_connection import ChannelConnectionCheckRead
from app.services.channel_service import check_channel_connection, connect_channel
from app.services.crud import create_entity, get_entity_or_404, update_entity
from app.services.tariff_policy import enforce_channel_limit

router = APIRouter(tags=["channels"])


@router.post("/projects/{project_id}/channels", response_model=TelegramChannelRead, status_code=status.HTTP_201_CREATED)
def create_channel(project_id: UUID, payload: TelegramChannelCreate, db: Session = Depends(get_db)):
    project = get_entity_or_404(db, Project, project_id, "Project not found")
    enforce_channel_limit(db, project=project)
    return create_entity(db, TelegramChannel, payload, project_id=project_id)


@router.get("/projects/{project_id}/channels", response_model=list[TelegramChannelRead])
def list_channels(project_id: UUID, db: Session = Depends(get_db)):
    return db.query(TelegramChannel).filter(TelegramChannel.project_id == project_id).all()


@router.get("/channels/{channel_id}", response_model=TelegramChannelRead)
def get_channel(channel_id: UUID, db: Session = Depends(get_db)):
    return get_entity_or_404(db, TelegramChannel, channel_id, "Channel not found")


@router.patch("/channels/{channel_id}", response_model=TelegramChannelRead)
def update_channel(channel_id: UUID, payload: TelegramChannelUpdate, db: Session = Depends(get_db)):
    channel = get_entity_or_404(db, TelegramChannel, channel_id, "Channel not found")
    return update_entity(db, channel, payload)


@router.post('/channels/{channel_id}/connect', response_model=TelegramChannelRead)
def connect_channel_endpoint(channel_id: UUID, payload: TelegramChannelUpdate, db: Session = Depends(get_db)):
    return connect_channel(db, channel_id, payload)


@router.get('/channels/{channel_id}/connection-check', response_model=ChannelConnectionCheckRead)
def check_channel_connection_endpoint(channel_id: UUID, db: Session = Depends(get_db)):
    return check_channel_connection(db, channel_id)
