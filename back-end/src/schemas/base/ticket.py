from sqlmodel import Column, Field, SQLModel, Text

from utilities.enumerables import TicketPriority, TicketStatus, TicketType


class TicketBase(SQLModel):
    subject: str = Field(..., max_length=255, index=True)
    description: str = Field(default=None, sa_column=Column(Text))

    answer: str | None = Field(default=None)
    image_url: str | None = Field(default=None)

    status: TicketStatus = Field(default=TicketStatus.OPEN, index=True)
    ticket_type: TicketType = Field(...)
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, index=True)
