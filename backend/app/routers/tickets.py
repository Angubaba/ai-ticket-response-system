from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Ticket
from ..schemas import ResponseUpdate, TicketCreate, TicketList, TicketOut, TicketUpdate
from ..services import fields as fields_svc
from ..services import pipeline

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _out(t: Ticket) -> TicketOut:
    out = TicketOut.model_validate(t)
    out.custom_fields = fields_svc.custom_fields_dict(t)
    return out


def _get_or_404(db: Session, ticket_id: int) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "ticket not found")
    return t


def _validate_fields(db: Session, payload: dict, partial: bool):
    try:
        return fields_svc.validate_and_normalize(db, payload, partial=partial)
    except fields_svc.FieldValidationError as e:
        raise HTTPException(422, {"message": "custom field validation failed", "errors": e.errors})


@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, background: BackgroundTasks, db: Session = Depends(get_db)):
    normalized = _validate_fields(db, body.custom_fields, partial=False)

    ticket = Ticket(**body.model_dump(exclude={"custom_fields"}))
    db.add(ticket)
    db.flush()
    fields_svc.save_values(db, ticket, normalized)
    db.commit()  # ticket is safely stored before any AI step runs

    pipeline.run_prediction(db, ticket)
    db.commit()
    if ticket.ai_status == "pending":
        background.add_task(pipeline.generate_draft, ticket.id)
    db.refresh(ticket)
    return _out(ticket)


@router.get("", response_model=TicketList)
def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    q: str | None = Query(None, description="search subject / customer / description"),
    include_inactive: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    conds = []
    if not include_inactive:
        conds.append(Ticket.is_active.is_(True))
    if status:
        conds.append(Ticket.status == status)
    if priority:
        conds.append(Ticket.priority == priority)
    if q:
        like = f"%{q}%"
        conds.append(or_(Ticket.subject.ilike(like), Ticket.customer_name.ilike(like), Ticket.description.ilike(like)))

    total = db.scalar(select(func.count()).select_from(Ticket).where(*conds)) or 0
    rows = db.scalars(select(Ticket).where(*conds).order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit).offset(offset))
    return TicketList(items=[_out(t) for t in rows], total=total)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    return _out(_get_or_404(db, ticket_id))


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, body: TicketUpdate, db: Session = Depends(get_db)):
    ticket = _get_or_404(db, ticket_id)
    data = body.model_dump(exclude_unset=True)
    custom = data.pop("custom_fields", None)
    normalized = _validate_fields(db, custom, partial=True) if custom is not None else {}

    for k, v in data.items():
        setattr(ticket, k, v)
    fields_svc.save_values(db, ticket, normalized)
    db.commit()
    db.refresh(ticket)
    return _out(ticket)


@router.put("/{ticket_id}/response", response_model=TicketOut)
def save_final_response(ticket_id: int, body: ResponseUpdate, db: Session = Depends(get_db)):
    """Agent reviews/edits the AI draft and saves the approved version."""
    ticket = _get_or_404(db, ticket_id)
    ticket.final_response = body.final_response.strip()
    db.commit()
    db.refresh(ticket)
    return _out(ticket)


@router.post("/{ticket_id}/regenerate", response_model=TicketOut, status_code=202)
def regenerate(
    ticket_id: int,
    background: BackgroundTasks,
    repredict: bool = False,
    db: Session = Depends(get_db),
):
    """Re-run the LLM draft (and optionally the ML prediction). Also the retry path after a local-model failure."""
    ticket = _get_or_404(db, ticket_id)
    if repredict:
        pipeline.run_prediction(db, ticket)
        db.commit()
    if not ticket.predicted_solution:
        raise HTTPException(409, ticket.ai_error or "no predicted solution available")
    ticket.ai_status = "pending"
    db.commit()
    background.add_task(pipeline.generate_draft, ticket.id, force=True)
    db.refresh(ticket)
    return _out(ticket)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int, hard: bool = False, db: Session = Depends(get_db)):
    ticket = _get_or_404(db, ticket_id)
    if hard:
        db.delete(ticket)
    else:
        ticket.is_active = False
    db.commit()
