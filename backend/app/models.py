from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | in_progress | resolved | closed

    # ML output
    predicted_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # RAG + LLM output
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)  # generated draft
    final_response: Mapped[str | None] = mapped_column(Text, nullable=True)  # agent-approved/edited
    ai_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | generating | done | failed | skipped
    ai_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    field_values: Mapped[list["TicketFieldValue"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", lazy="selectin"
    )


class FieldDefinition(Base):
    """Admin-defined custom field. Adding one is a row insert, never a migration."""

    __tablename__ = "field_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(20))  # text | dropdown | number | date | checkbox
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # dropdown choices
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TicketFieldValue(Base):
    """EAV row: one value of one custom field on one ticket. Stored as normalized text."""

    __tablename__ = "ticket_field_values"
    __table_args__ = (UniqueConstraint("ticket_id", "field_id", name="uq_ticket_field"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id", ondelete="CASCADE"), index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    ticket: Mapped[Ticket] = relationship(back_populates="field_values")
    field: Mapped[FieldDefinition] = relationship(lazy="joined")
