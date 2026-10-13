from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FieldType = Literal["text", "dropdown", "number", "date", "checkbox"]
Status = Literal["open", "in_progress", "resolved", "closed"]
Priority = Literal["low", "medium", "high", "urgent"]


# ---------- dynamic fields ----------
class FieldDefinitionIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,59}$", description="snake_case identifier")
    label: str = Field(min_length=1, max_length=120)
    field_type: FieldType
    required: bool = False
    options: list[str] | None = None
    sort_order: int = 0


class FieldDefinitionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    required: bool | None = None
    options: list[str] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class FieldDefinitionOut(FieldDefinitionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool


# ---------- tickets ----------
class TicketCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=5)
    category: str | None = None
    priority: Priority = "medium"
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class TicketUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=120)
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=5)
    category: str | None = None
    priority: Priority | None = None
    status: Status | None = None
    custom_fields: dict[str, Any] | None = None


class ResponseUpdate(BaseModel):
    final_response: str = Field(min_length=1)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    subject: str
    description: str
    category: str | None
    priority: str
    status: str
    predicted_solution: str | None
    ml_confidence: float | None
    ai_response: str | None
    final_response: str | None
    ai_sources: list | None
    ai_status: str
    ai_error: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class TicketList(BaseModel):
    items: list[TicketOut]
    total: int


class HealthOut(BaseModel):
    api: str = "ok"
    database: bool
    ml_model: bool
    ollama: bool
    ollama_model_available: bool
    knowledge_base_chunks: int
