import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import Base, engine
from .routers import fields, tickets
from .schemas import HealthOut
from .seed import seed_default_fields
from .services import llm as llm_mod
from .services import ml as ml_mod
from .services import rag as rag_mod

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")


def _warm_knowledge_base() -> None:
    try:
        n = rag_mod.get_knowledge_base().index()
        log.info("Knowledge base ready: %s chunks (%s)", n, rag_mod.get_knowledge_base().backend)
    except Exception:
        log.exception("Knowledge base indexing failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed_default_fields()
    # index in the background so the API is up immediately (first run downloads the embedding model)
    threading.Thread(target=_warm_knowledge_base, daemon=True).start()
    yield


app = FastAPI(title="AI Customer Ticket Response System", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tickets.router)
app.include_router(fields.router)


@app.get("/api/health", response_model=HealthOut, tags=["system"])
def health():
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    reachable, model_ok = llm_mod.get_llm_client().health()
    kb = rag_mod.get_knowledge_base()
    return HealthOut(
        database=db_ok,
        ml_model=ml_mod.get_model().available,
        ollama=reachable,
        ollama_model_available=model_ok,
        knowledge_base_chunks=len(kb.chunks),
    )
