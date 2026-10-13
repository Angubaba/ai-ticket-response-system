from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FieldDefinition
from ..schemas import FieldDefinitionIn, FieldDefinitionOut, FieldDefinitionUpdate

router = APIRouter(prefix="/api/fields", tags=["dynamic fields"])


def _check_options(field_type: str, options: list[str] | None) -> None:
    if field_type == "dropdown" and not options:
        raise HTTPException(422, "dropdown fields need at least one option")


@router.get("", response_model=list[FieldDefinitionOut])
def list_fields(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = select(FieldDefinition).order_by(FieldDefinition.sort_order, FieldDefinition.id)
    if not include_inactive:
        q = q.where(FieldDefinition.is_active.is_(True))
    return list(db.scalars(q))


@router.post("", response_model=FieldDefinitionOut, status_code=201)
def create_field(body: FieldDefinitionIn, db: Session = Depends(get_db)):
    if db.scalar(select(FieldDefinition).where(FieldDefinition.key == body.key)):
        raise HTTPException(409, f"field key '{body.key}' already exists")
    _check_options(body.field_type, body.options)
    f = FieldDefinition(**body.model_dump())
    db.add(f)
    db.commit()
    return f


@router.patch("/{field_id}", response_model=FieldDefinitionOut)
def update_field(field_id: int, body: FieldDefinitionUpdate, db: Session = Depends(get_db)):
    f = db.get(FieldDefinition, field_id)
    if not f:
        raise HTTPException(404, "field not found")
    data = body.model_dump(exclude_unset=True)
    if "options" in data:
        _check_options(f.field_type, data["options"])
    for k, v in data.items():
        setattr(f, k, v)
    db.commit()
    return f


@router.delete("/{field_id}", status_code=204)
def deactivate_field(field_id: int, db: Session = Depends(get_db)):
    """Soft delete: keeps historical values on tickets intact."""
    f = db.get(FieldDefinition, field_id)
    if not f:
        raise HTTPException(404, "field not found")
    f.is_active = False
    db.commit()
