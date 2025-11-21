from datetime import datetime
from sqlmodel import UUID, Column, Field, SQLModel, Text

from schemas.base.ticket import TicketBase
from utilities.enumerables import TicketPriority, TicketStatus, TicketType


class TicketPublic(TicketBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class TicketCreate(TicketBase):
    requester_user_id: UUID


class TicketUpdate(SQLModel):
    subject: str | None = Field(default=None, max_length=255, index=True)
    description: str | None = Field(default=None, sa_column=Column(Text))

    answer: str | None = Field(default=None)
    image_url: str | None = Field(default=None)

    status: TicketStatus | None = Field(default=None, index=True)
    ticket_type: TicketType | None = Field(default=None,)
    priority: TicketPriority | None = Field(default=None, index=True)
