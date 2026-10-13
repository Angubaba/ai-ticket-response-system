"""Ticket AI pipeline: ML prediction (sync) -> RAG + local LLM draft (background)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Ticket
from . import llm as llm_mod
from . import ml as ml_mod
from . import rag as rag_mod

log = logging.getLogger(__name__)

INSUFFICIENT = "INSUFFICIENT_CONTEXT"

SYSTEM_PROMPT = f"""You are a customer support assistant. Write a reply to the customer using ONLY the information in the KNOWLEDGE BASE EXCERPTS.

Rules:
- Be warm, clear and concise. Start with a brief apology or acknowledgement, then give the steps.
- Use only facts, steps, menu names, time limits and policies that appear in the excerpts. Do not invent anything.
- Do not promise refunds, deadlines, discounts or actions that the excerpts do not state.
- The SUGGESTED SOLUTION is a hint about what the customer needs. Follow it only where the excerpts support it.
- If the excerpts do not contain enough information to help with this ticket, reply with exactly {INSUFFICIENT} and nothing else.
- Address the customer by name. Sign off as "Customer Support Team". No placeholders, no markdown headings."""


def build_user_prompt(ticket: Ticket, solution: str, chunks: list[rag_mod.Chunk]) -> str:
    excerpts = "\n\n".join(f"[{i}] ({c.source} - {c.title})\n{c.text}" for i, c in enumerate(chunks, 1))
    return (
        f"KNOWLEDGE BASE EXCERPTS:\n{excerpts}\n\n"
        f"TICKET\nCustomer: {ticket.customer_name}\nSubject: {ticket.subject}\n"
        f"Description: {ticket.description}\n\n"
        f"SUGGESTED SOLUTION (from classifier): {solution}\n\n"
        "Write the reply to the customer now."
    )


def retrieval_query(ticket: Ticket) -> str:
    parts = [ticket.subject, ticket.description]
    if ticket.predicted_solution and ticket.predicted_solution != ml_mod.ESCALATION_SOLUTION:
        parts.append(ticket.predicted_solution)
    return " ".join(parts)


def run_prediction(db: Session, ticket: Ticket) -> None:
    """Step 3-4 of the workflow. Never raises: failures are recorded on the ticket."""
    try:
        pred = ml_mod.get_model().predict(ticket.subject, ticket.description)
    except ml_mod.ModelUnavailable as e:
        ticket.predicted_solution = None
        ticket.ml_confidence = None
        ticket.ai_status = "failed"
        ticket.ai_error = f"ML prediction unavailable: {e}"
        return
    except Exception as e:  # pragma: no cover - defensive
        log.exception("ML prediction crashed")
        ticket.ai_status = "failed"
        ticket.ai_error = f"ML prediction failed: {e}"
        return

    ticket.predicted_solution = pred.solution
    ticket.ml_confidence = pred.confidence
    if ticket.category is None and pred.category:
        ticket.category = pred.category
    if pred.low_confidence:
        ticket.ai_status = "skipped"
        ticket.ai_error = (
            f"Model confidence {pred.confidence:.0%} is below the threshold, so no AI draft was generated. "
            "Handle this ticket manually, or use Regenerate to force a draft."
        )
    else:
        ticket.ai_status = "pending"
        ticket.ai_error = None


def generate_draft(ticket_id: int, *, force: bool = False) -> None:
    """Steps 5-6: retrieve KB context and draft the reply with the local LLM. Safe to run in background."""
    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            return
        if ticket.ai_status == "skipped" and not force:
            return
        if not ticket.predicted_solution:
            ticket.ai_status = "failed"
            ticket.ai_error = ticket.ai_error or "No predicted solution to expand."
            db.commit()
            return

        ticket.ai_status = "generating"
        ticket.ai_error = None
        db.commit()

        # --- retrieve ---
        try:
            chunks = rag_mod.get_knowledge_base().search(retrieval_query(ticket))
        except Exception as e:
            log.exception("retrieval failed")
            ticket.ai_status, ticket.ai_error = "failed", f"Knowledge-base retrieval failed: {e}"
            db.commit()
            return

        if not chunks:
            ticket.ai_status = "failed"
            ticket.ai_sources = []
            ticket.ai_error = "No relevant knowledge-base content found, so no draft was generated (avoids made-up answers)."
            db.commit()
            return

        # --- generate ---
        try:
            text = llm_mod.get_llm_client().chat(SYSTEM_PROMPT, build_user_prompt(ticket, ticket.predicted_solution, chunks))
        except llm_mod.LLMUnavailable as e:
            ticket.ai_status, ticket.ai_error = "failed", str(e)
            ticket.ai_sources = [c.public() for c in chunks]
            db.commit()
            return

        ticket.ai_sources = [c.public() for c in chunks]
        if text.strip().strip(".").upper() == INSUFFICIENT:
            ticket.ai_status = "failed"
            ticket.ai_error = "The knowledge base doesn't cover this ticket well enough; the model declined to draft a reply."
        else:
            ticket.ai_response = text
            ticket.ai_status = "done"
            ticket.ai_error = None
        db.commit()
    except Exception as e:  # last-resort guard so a background task never dies silently
        log.exception("draft generation crashed")
        db.rollback()
        t = db.get(Ticket, ticket_id)
        if t:
            t.ai_status, t.ai_error = "failed", f"Unexpected error: {e}"
            db.commit()
    finally:
        db.close()
