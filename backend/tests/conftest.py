import os
import tempfile
from pathlib import Path

# must be set before the app is imported
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ["CHROMA_DIR"] = str(Path(_tmp) / "chroma")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.services import llm as llm_mod
from app.services import ml as ml_mod
from app.services import rag as rag_mod


class FakeLLM:
    """Echoes the KB excerpt it was given so tests can prove retrieval influenced the output."""

    def __init__(self):
        self.calls = []
        self.fail_with = None
        self.reply = None

    def chat(self, system, user, temperature=0.2):
        self.calls.append((system, user))
        if self.fail_with:
            raise llm_mod.LLMUnavailable(self.fail_with)
        if self.reply is not None:
            return self.reply
        marker = "KNOWLEDGE BASE EXCERPTS:"
        excerpt = user.split(marker, 1)[1].split("TICKET", 1)[0].strip()
        return f"Hello, here is how to fix it. {excerpt[:300]}"

    def health(self):
        return True, True


@pytest.fixture(scope="session", autouse=True)
def _train_and_index():
    if not ml_mod.get_model().available:
        ml_mod.train()
    kb = rag_mod.KnowledgeBase(chroma_dir=Path(_tmp) / "chroma")
    # force the lexical retriever: tests must not need to download embedding weights
    kb.chunks = rag_mod.load_chunks(kb.kb_dir)
    kb._index_lexical()
    kb.backend = "tfidf-fallback"
    kb._ready = True
    rag_mod._kb = kb


@pytest.fixture()
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm_mod, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture()
def client(fake_llm):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from app.seed import seed_default_fields

    seed_default_fields()
    with TestClient(app) as c:  # lifespan runs; background tasks execute before the response returns
        yield c


BASE_TICKET = {
    "customer_name": "Asha Verma",
    "subject": "Unable to log in",
    "description": "I forgot my password and cannot access my account.",
    "custom_fields": {"product": "Web dashboard"},
}
