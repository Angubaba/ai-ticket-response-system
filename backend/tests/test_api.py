import pytest

from app.services import ml as ml_mod
from app.services import rag as rag_mod

from .conftest import BASE_TICKET


def make(client, **over):
    body = {**BASE_TICKET, **over}
    r = client.post("/api/tickets", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- CRUD ----------
def test_crud_lifecycle(client):
    t = make(client)
    tid = t["id"]

    got = client.get(f"/api/tickets/{tid}").json()
    assert got["subject"] == "Unable to log in"

    r = client.patch(f"/api/tickets/{tid}", json={"status": "in_progress", "priority": "high"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["priority"] == "high"

    listing = client.get("/api/tickets").json()
    assert listing["total"] == 1

    assert client.delete(f"/api/tickets/{tid}").status_code == 204
    assert client.get("/api/tickets").json()["total"] == 0  # soft-deleted hidden
    assert client.get("/api/tickets?include_inactive=true").json()["total"] == 1
    assert client.get(f"/api/tickets/{tid}").json()["is_active"] is False


def test_hard_delete_and_404(client):
    tid = make(client)["id"]
    assert client.delete(f"/api/tickets/{tid}?hard=true").status_code == 204
    assert client.get(f"/api/tickets/{tid}").status_code == 404


def test_validation_rejects_bad_input(client):
    r = client.post("/api/tickets", json={"customer_name": "", "subject": "x", "description": "y"})
    assert r.status_code == 422


def test_filter_and_search(client):
    make(client)
    make(client, subject="Charged twice", description="I was charged twice for the same order this month.", priority="urgent")
    assert client.get("/api/tickets?priority=urgent").json()["total"] == 1
    assert client.get("/api/tickets?q=charged").json()["total"] == 1


# ---------- ML ----------
@pytest.mark.parametrize(
    "subject,desc,expected",
    [
        ("Unable to log in", "I forgot my password and cannot access my account.", "Reset the password"),
        ("Charged twice", "I see two identical charges on my credit card for one subscription.", "refund for the duplicate charge"),
        ("Where is my order", "My delivery is late and I want to know where my parcel is right now.", "Track the order"),
        ("App keeps crashing", "The mobile app crashes every time I open it.", "Clear the app cache"),
    ],
)
def test_ml_predicts_different_ticket_types(client, subject, desc, expected):
    t = make(client, subject=subject, description=desc)
    assert expected in t["predicted_solution"]
    assert t["ml_confidence"] > 0.25


def test_category_is_filled_from_prediction_when_missing(client):
    assert make(client)["category"] == "Account"


def test_low_confidence_is_escalated_not_guessed(client, fake_llm):
    t = make(client, subject="Rayleigh scattering", description="Why is the sky blue during the day?")
    assert t["predicted_solution"] == ml_mod.ESCALATION_SOLUTION
    assert t["ai_status"] == "skipped"
    assert fake_llm.calls == []  # LLM never called


# ---------- RAG + LLM ----------
def test_draft_generated_and_saved_with_sources(client, fake_llm):
    t = make(client)
    got = client.get(f"/api/tickets/{t['id']}").json()
    assert got["ai_status"] == "done"
    assert got["ai_response"]
    assert got["ai_sources"] and got["ai_sources"][0]["source"] == "account_access.md"


def test_kb_content_influences_prompt_and_output(client, fake_llm):
    make(client)
    system, user = fake_llm.calls[-1]
    assert "Forgot Password option on the login page" in user  # retrieved text reached the LLM
    assert "Reset the password using the account recovery process." in user  # ML output reached the LLM
    assert "ONLY" in system  # grounding instruction present


def test_different_tickets_retrieve_different_kb_sections(client, fake_llm):
    make(client)
    make(client, subject="Where is my order", description="My delivery is late and I want to know where my parcel is right now.")
    pw_prompt = fake_llm.calls[0][1]
    ship_prompt = fake_llm.calls[1][1]
    assert "shipping_orders.md" in ship_prompt and "shipping_orders.md" not in pw_prompt


def test_insufficient_context_marker_is_handled(client, fake_llm):
    fake_llm.reply = "INSUFFICIENT_CONTEXT"
    t = make(client)
    got = client.get(f"/api/tickets/{t['id']}").json()
    assert got["ai_status"] == "failed" and got["ai_response"] is None
    assert "doesn't cover" in got["ai_error"]


def test_agent_can_edit_and_save_final_response(client):
    tid = make(client)["id"]
    r = client.put(f"/api/tickets/{tid}/response", json={"final_response": "  Edited reply.  "})
    assert r.status_code == 200 and r.json()["final_response"] == "Edited reply."
    assert client.get(f"/api/tickets/{tid}").json()["ai_response"]  # original draft preserved


# ---------- graceful failure ----------
def test_ticket_still_saved_when_llm_down_and_retry_works(client, fake_llm):
    fake_llm.fail_with = "Cannot reach Ollama at http://localhost:11434. Is it running?"
    t = make(client)
    got = client.get(f"/api/tickets/{t['id']}").json()
    assert got["ai_status"] == "failed" and "Ollama" in got["ai_error"]
    assert got["predicted_solution"]  # ML output kept

    fake_llm.fail_with = None
    r = client.post(f"/api/tickets/{t['id']}/regenerate")
    assert r.status_code == 202
    assert client.get(f"/api/tickets/{t['id']}").json()["ai_status"] == "done"


def test_ticket_still_saved_when_ml_model_missing(client, monkeypatch):
    class Broken:
        def predict(self, *a, **k):
            raise ml_mod.ModelUnavailable("model file not found")

    monkeypatch.setattr(ml_mod, "get_model", lambda: Broken())
    r = client.post("/api/tickets", json=BASE_TICKET)
    assert r.status_code == 201
    body = r.json()
    assert body["predicted_solution"] is None and body["ai_status"] == "failed"
    assert "ML prediction unavailable" in body["ai_error"]
    assert client.post(f"/api/tickets/{body['id']}/regenerate").status_code == 409


def test_no_relevant_kb_content_means_no_draft(client, fake_llm, monkeypatch):
    class EmptyKB:
        chunks = []

        def search(self, q, k=None):
            return []

    monkeypatch.setattr(rag_mod, "get_knowledge_base", lambda: EmptyKB())
    t = make(client)
    got = client.get(f"/api/tickets/{t['id']}").json()
    assert got["ai_status"] == "failed" and "No relevant knowledge-base" in got["ai_error"]
    assert fake_llm.calls == []


# ---------- dynamic fields ----------
def test_field_definitions_load_dynamically(client):
    keys = [f["key"] for f in client.get("/api/fields").json()]
    assert {"order_number", "product", "units_affected", "issue_date", "customer_verified"} <= set(keys)


def test_new_field_usable_without_schema_change(client):
    r = client.post("/api/fields", json={"key": "region", "label": "Region", "field_type": "dropdown", "options": ["EU", "US"], "required": True})
    assert r.status_code == 201
    # now required on new tickets
    assert client.post("/api/tickets", json=BASE_TICKET).status_code == 422
    t = make(client, custom_fields={"product": "Mobile app", "region": "EU"})
    assert t["custom_fields"]["region"] == "EU"


@pytest.mark.parametrize(
    "fields,bad_key",
    [
        ({"product": "Toaster"}, "product"),  # not in dropdown options
        ({"product": "Mobile app", "units_affected": "lots"}, "units_affected"),  # not a number
        ({"product": "Mobile app", "issue_date": "13/10/2026"}, "issue_date"),  # not ISO date
        ({"product": "Mobile app", "customer_verified": "maybe"}, "customer_verified"),  # not a bool
        ({"product": "Mobile app", "nope": 1}, "nope"),  # unknown field
        ({}, "product"),  # required missing
    ],
)
def test_custom_field_validation(client, fields, bad_key):
    r = client.post("/api/tickets", json={**BASE_TICKET, "custom_fields": fields})
    assert r.status_code == 422
    assert bad_key in r.json()["detail"]["errors"]


def test_all_field_types_roundtrip(client):
    cf = {
        "order_number": "ORD-1001",
        "product": "Smart device",
        "units_affected": 3,
        "issue_date": "2026-10-01",
        "customer_verified": True,
    }
    t = make(client, custom_fields=cf)
    assert client.get(f"/api/tickets/{t['id']}").json()["custom_fields"] == cf


def test_partial_update_of_custom_fields(client):
    t = make(client)
    r = client.patch(f"/api/tickets/{t['id']}", json={"custom_fields": {"order_number": "ORD-7"}})
    assert r.status_code == 200
    assert r.json()["custom_fields"]["order_number"] == "ORD-7"
    assert r.json()["custom_fields"]["product"] == "Web dashboard"  # untouched


def test_deactivated_field_stops_being_required(client):
    fid = next(f["id"] for f in client.get("/api/fields").json() if f["key"] == "product")
    assert client.delete(f"/api/fields/{fid}").status_code == 204
    r = client.post("/api/tickets", json={**BASE_TICKET, "custom_fields": {}})
    assert r.status_code == 201


def test_dropdown_needs_options(client):
    r = client.post("/api/fields", json={"key": "tier", "label": "Tier", "field_type": "dropdown"})
    assert r.status_code == 422


def test_duplicate_field_key_conflict(client):
    r = client.post("/api/fields", json={"key": "product", "label": "dup", "field_type": "text"})
    assert r.status_code == 409


# ---------- health ----------
def test_health(client):
    h = client.get("/api/health").json()
    assert h["database"] and h["ml_model"] and h["knowledge_base_chunks"] > 0


# ---------- unit ----------
def test_chunker_splits_on_headings():
    chunks = rag_mod.chunk_markdown("# T\n\n## A\nalpha body\n\n## B\nbeta body\n", "x.md")
    assert [c.title for c in chunks] == ["A", "B"] and "alpha body" in chunks[0].text


# ---------- dense retrieval path (Chroma) with a stub embedder ----------
def test_chroma_index_search_and_persistence(tmp_path):
    chromadb = pytest.importorskip("chromadb")  # noqa: F841
    import hashlib

    import numpy as np

    calls = {"n": 0}

    class Stub:
        model_name = "stub"

        def encode(self, texts, query=False):
            calls["n"] += len(texts)
            out = []
            for t in texts:
                v = np.zeros(256)
                for w in t.lower().split():
                    v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1
                out.append((v / (np.linalg.norm(v) or 1)).tolist())
            return out

    kb = rag_mod.KnowledgeBase(chroma_dir=tmp_path, embedder=Stub())
    assert kb.index() > 0 and kb.backend == "chroma+embeddings"  # catches invalid collection names etc.
    kb.min_score  # property exists
    from app.config import settings

    old, settings.rag_min_score = settings.rag_min_score, 0.1
    try:
        hits = kb.search("forgot password login reset link email")
        assert hits and hits[0].source == "account_access.md"
    finally:
        settings.rag_min_score = old

    first = calls["n"]
    kb2 = rag_mod.KnowledgeBase(chroma_dir=tmp_path, embedder=Stub())
    kb2.index()
    assert kb2.backend == "chroma+embeddings" and calls["n"] == first  # nothing re-embedded
