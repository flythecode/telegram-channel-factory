from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedSchema


class UserBase(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    telegram_user_id: str | None = Field(default=None, max_length=64)
    is_active: bool = True
    preferences: dict[str, Any] | None = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    telegram_user_id: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None
    preferences: dict[str, Any] | None = None


class UserRead(TimestampedSchema):
    email: str
    full_name: str | None
    telegram_user_id: str | None
    is_active: bool
    preferences: dict[str, Any] | None
