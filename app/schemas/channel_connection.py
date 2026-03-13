from pydantic import BaseModel


class ChannelConnectionCheckRead(BaseModel):
    is_connected: bool
    bot_is_admin: bool
    can_post_messages: bool
    status: str
