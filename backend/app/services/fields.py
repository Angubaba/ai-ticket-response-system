"""Validation + (de)serialization for dynamic custom fields (EAV)."""
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FieldDefinition, Ticket, TicketFieldValue


class FieldValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(str(errors))


def _is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _normalize(defn: FieldDefinition, raw: Any) -> str | None:
    """Validate raw against the definition. Returns normalized storage string. Raises ValueError."""
    t = defn.field_type
    if t == "checkbox":
        if raw is None:  # unchecked boxes are often omitted by clients
            return "false"
        if isinstance(raw, bool):
            return "true" if raw else "false"
        if isinstance(raw, str) and raw.lower() in ("true", "false"):
            return raw.lower()
        raise ValueError("must be true or false")
    if _is_empty(raw):
        return None
    if t == "text":
        return str(raw).strip()
    if t == "number":
        if isinstance(raw, bool):
            raise ValueError("must be a number")
        try:
            n = float(raw)
        except (TypeError, ValueError):
            raise ValueError("must be a number")
        return str(int(n)) if n.is_integer() else str(n)
    if t == "date":
        try:
            return date.fromisoformat(str(raw)).isoformat()
        except ValueError:
            raise ValueError("must be an ISO date (YYYY-MM-DD)")
    if t == "dropdown":
        if str(raw) not in (defn.options or []):
            raise ValueError(f"must be one of {defn.options}")
        return str(raw)
    raise ValueError(f"unsupported field type {t}")


def _deserialize(defn: FieldDefinition, stored: str | None) -> Any:
    if defn.field_type == "checkbox":
        return stored == "true"
    if stored is None:
        return None
    if defn.field_type == "number":
        n = float(stored)
        return int(n) if n.is_integer() else n
    return stored


def active_definitions(db: Session) -> list[FieldDefinition]:
    return list(
        db.scalars(
            select(FieldDefinition).where(FieldDefinition.is_active.is_(True)).order_by(FieldDefinition.sort_order, FieldDefinition.id)
        )
    )


def validate_and_normalize(
    db: Session, payload: dict[str, Any], *, partial: bool = False
) -> dict[int, str | None]:
    """Returns {field_id: normalized_value}. Raises FieldValidationError with per-key messages.

    partial=True (updates) only enforces `required` for keys that were actually sent.
    """
    defs = {d.key: d for d in active_definitions(db)}
    errors: dict[str, str] = {}
    out: dict[int, str | None] = {}

    for key in payload:
        if key not in defs:
            errors[key] = "unknown field"

    for key, defn in defs.items():
        if partial and key not in payload:
            continue
        raw = payload.get(key)
        try:
            norm = _normalize(defn, raw)
        except ValueError as e:
            errors[key] = str(e)
            continue
        if defn.required and defn.field_type != "checkbox" and norm is None:
            errors[key] = "required"
            continue
        out[defn.id] = norm

    if errors:
        raise FieldValidationError(errors)
    return out


def save_values(db: Session, ticket: Ticket, normalized: dict[int, str | None]) -> None:
    existing = {fv.field_id: fv for fv in ticket.field_values}
    for field_id, value in normalized.items():
        if field_id in existing:
            existing[field_id].value = value
        else:
            ticket.field_values.append(TicketFieldValue(field_id=field_id, value=value))


def custom_fields_dict(ticket: Ticket) -> dict[str, Any]:
    return {fv.field.key: _deserialize(fv.field, fv.value) for fv in ticket.field_values if fv.field.is_active}
