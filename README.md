# AI Customer Ticket Response System

Demo video : https://drive.google.com/file/d/17Y4JNiq35w0WzjOG-S6QwWG8aADlDfWB/view?usp=sharing

A web app for managing customer support tickets. When a ticket is created, a **local ML model** predicts a one-line solution, then a **local LLM with RAG** expands it into a detailed, customer-friendly reply grounded in a local knowledge base. The agent reviews, edits and saves the final response.

**Everything runs locally. No cloud AI APIs, no API keys, no secrets.**

| Layer | Choice |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| API | FastAPI + Pydantic v2 |
| Database | PostgreSQL 16 via SQLAlchemy 2 (SQLite fallback for dev/tests) |
| ML | scikit-learn: TF-IDF (word + char n-grams) → Logistic Regression |
| Embeddings | `BAAI/bge-small-en-v1.5` via sentence-transformers (CPU) |
| Vector store | ChromaDB (persistent, cosine) |
| LLM | Ollama, default `llama3.2:3b` |
| Packaging | Docker Compose |

---

## 1. Architecture

```
                    ┌────────────────────────── FastAPI backend ──────────────────────────┐
 React UI  ──HTTP──▶│ routers/tickets   routers/fields                                    │
 (Vite/Tailwind)    │      │                  │                                           │
                    │      ▼                  ▼                                           │
                    │ 1. save ticket ──▶ PostgreSQL  (tickets, field_definitions,         │
                    │      │                          ticket_field_values)                │
                    │      ▼                                                              │
                    │ 2. services/ml.py    TF-IDF + LogReg ──▶ one-line solution + conf.  │
                    │      │   (saved on ticket; low confidence ⇒ escalate, skip LLM)     │
                    │      ▼   ── background task, ticket already saved ──                │
                    │ 3. services/rag.py   query ─▶ bge-small embed ─▶ ChromaDB top-k     │
                    │      │               (below relevance floor ⇒ no draft)             │
                    │      ▼                                                              │
                    │ 4. services/llm.py   grounded prompt ─▶ Ollama (local) ─▶ draft     │
                    │      ▼                                                              │
                    │ 5. draft + sources saved; agent edits ─▶ final_response saved       │
                    └─────────────────────────────────────────────────────────────────────┘
```

Workflow mapping to the assessment: steps 1–2 happen synchronously in `POST /api/tickets`; steps 3–6 (retrieval + LLM) run as a background task so a slow local LLM never blocks ticket creation. The UI polls the ticket until the draft is ready. Steps 7–8 are `PUT /api/tickets/{id}/response`.

## 2. Quick start (Docker)

Prerequisites: Docker with Compose v2, ~6 GB free disk, 8 GB RAM recommended.

```bash
cp .env.example .env
docker compose up --build
```

First start downloads the Ollama model (~2 GB) and the embedding model (~130 MB); allow a few minutes. The UI header shows live status dots for DB / ML model / local LLM / knowledge base.

- UI: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/api/health

For an NVIDIA GPU, uncomment the `deploy` block under `ollama` in `docker-compose.yml`.

## 3. Local development (no Docker)

```bash
# --- LLM ---
ollama serve &                      # or the desktop app
ollama pull llama3.2:3b

# --- backend (SQLite by default, no DB setup needed) ---
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts_generate_dataset.py  # optional: regenerates data/tickets.csv
python -m app.cli train             # trains + saves models/solution_model.joblib
uvicorn app.main:app --reload       # http://localhost:8000

# --- frontend ---
cd ../frontend
npm install
npm run dev                         # http://localhost:5173 (proxies /api to :8000)
```

To use Postgres locally, set `DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/tickets`.

### Database setup
Tables are created automatically on startup (`Base.metadata.create_all`) and five sample custom fields are seeded on an empty DB. The equivalent PostgreSQL DDL is in [`backend/schema.sql`](backend/schema.sql).

## 4. Configuration

All settings are environment variables (or `backend/.env`); defaults are in `backend/app/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite file | SQLAlchemy URL |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / `llama3.2:3b` | Local LLM. `qwen2.5:3b` or `llama3.1:8b` also work |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local sentence-transformers model |
| `ML_MIN_CONFIDENCE` | `0.25` | Below this the ticket is escalated instead of guessed |
| `RAG_TOP_K` | `3` | Chunks passed to the LLM |
| `RAG_MIN_SCORE` | `0.45` | Cosine-similarity floor for dense retrieval |
| `LLM_TIMEOUT_S` | `120` | Ollama request timeout |

## 5. ML solution prediction

**Task.** Map (subject + description) → one of a fixed set of approved one-line solutions. This is framed as **text classification**, where each class label *is* the solution sentence. That keeps outputs predictable and auditable (a classifier can't hallucinate a policy), and leaves the creative expansion to the LLM stage.

**Model selection.** `TfidfVectorizer` on words (1–2 grams) and characters (3–5 grams, `char_wb`, robust to typos and "logn"/"login" variants) feeding a `LogisticRegression` (`C=10`, `class_weight=balanced`). Why not something heavier: with a few hundred short examples, linear models on TF-IDF are hard to beat, train in a second on CPU, are calibrated enough to threshold on, and need no GPU. The subject is repeated in the input text to up-weight it.

**Training data.** `backend/data/tickets.csv`: 640 synthetic tickets, 16 solution classes across Account, Billing, Shipping, Technical, Privacy and Product. It is generated by `scripts_generate_dataset.py` (seeded, template + paraphrase + noise prefixes/suffixes). No real customer data. Replace the CSV with real labelled tickets (same four columns: `subject, description, category, solution`) and run `python -m app.cli train`.

**Prediction process.** `predict_proba` → top class + confidence. The solution, confidence and the class's category are saved on the ticket (category only fills in if the agent left it blank). If confidence < `ML_MIN_CONFIDENCE`, the solution becomes *"Escalate to a human support agent for manual triage."*, the LLM stage is skipped, and the UI says so, so off-topic tickets don't get a confident wrong answer.

**Evaluation caveat.** `app.cli train` reports 5-fold stratified CV accuracy of 1.0. **Treat that as meaningless**: the data is templated, so folds contain near-duplicates of each other. It shows the pipeline works, not real-world accuracy. Spot checks on unseen phrasings behave sensibly (see tests), but you would need real held-out tickets to quote an honest number.

## 6. LLM + RAG workflow

1. **Knowledge base.** Markdown files in `backend/kb/`, split into one chunk per `##` section (so each chunk is one self-contained policy).
2. **Indexing.** Chunks are embedded locally and stored in ChromaDB (`chroma_store/`). A content hash means restarts skip re-embedding unless the KB changed. Add or edit a `.md` file and restart (or `python -m app.cli reindex`).
3. **Retrieval.** Query = subject + description + the ML-predicted solution. Top-k by cosine similarity; anything under `RAG_MIN_SCORE` is dropped.
4. **Generation.** The system prompt restricts the model to the retrieved excerpts, forbids inventing steps/policies/promises, and defines an `INSUFFICIENT_CONTEXT` escape hatch. The user prompt contains the excerpts, the ticket and the ML solution as a hint. Temperature is 0.2.
5. **Storage.** The draft (`ai_response`), the retrieved sources with relevance scores, and status are saved. The agent edits in the UI and saves `final_response`; the original draft is preserved and restorable.

**Guards against unsupported content:** no relevant chunks ⇒ no LLM call; model replies `INSUFFICIENT_CONTEXT` ⇒ no draft is stored; sources are shown next to every draft so the agent can verify it. Small local models can still paraphrase loosely, which is why the draft is always reviewed by a human before it counts as final.

If the embedding model or ChromaDB can't load, retrieval automatically falls back to an in-memory TF-IDF retriever (still fully local) and `/api/health` reports it.

## 7. Dynamic fields

Three tables: `field_definitions` (key, label, type, required, options), `ticket_field_values` (ticket_id, field_id, value) and `tickets`. This is an EAV design: **adding a field is an INSERT, never an `ALTER TABLE`**.

- Types: text, dropdown, number, date, checkbox.
- The frontend fetches `/api/fields` and renders inputs from the definitions (`DynamicFields.tsx` has no field names in it).
- The backend validates per type (dropdown ∈ options, numeric, ISO date, boolean), enforces `required`, and rejects unknown keys with per-field error messages returned to the form.
- Fields are soft-deactivated, so historical values on old tickets survive.
- Manage them in the UI ("Custom fields") or via `POST /api/fields`.

Trade-off: values are stored as text, so SQL-side range queries on numbers/dates need a cast. Fine for a ticket desk, and it's the price of schemaless fields.

## 8. API summary

| Method & path | Purpose |
|---|---|
| `POST /api/tickets` | Create → saves, predicts, queues the draft |
| `GET /api/tickets` | List (`status`, `priority`, `q`, `include_inactive`, `limit`, `offset`) |
| `GET /api/tickets/{id}` | Detail (incl. custom fields, sources) |
| `PATCH /api/tickets/{id}` | Update info, status, custom fields |
| `PUT /api/tickets/{id}/response` | Save the agent-approved response |
| `POST /api/tickets/{id}/regenerate?repredict=` | Retry / redo the draft (and optionally the ML step) |
| `DELETE /api/tickets/{id}` | Deactivate (`?hard=true` to delete) |
| `GET/POST/PATCH/DELETE /api/fields` | Field definitions |
| `GET /api/health` | DB, ML model, Ollama, KB status |

## 9. Failure handling

| Situation | Behaviour |
|---|---|
| Ollama down / model not pulled / timeout | Ticket + ML prediction are kept; status `failed` with a specific message (e.g. "run `ollama pull …`"); **Retry draft** button; header banner |
| ML model file missing/corrupt | Ticket still saved; `ML prediction unavailable` shown; agent can still write a reply manually |
| Low ML confidence | Escalation text, LLM skipped, "Manual" badge; **Re-run** can force a draft |
| KB has nothing relevant | No draft generated, explained to the agent |
| Embedding model/Chroma unavailable | Falls back to TF-IDF retrieval |
| Invalid / missing custom fields | 422 with per-field messages shown inline |
| Backend unreachable | UI shows "Cannot reach the backend" |

## 10. Tests

```bash
cd backend && pytest -q        # 34 tests
```

Covers: CRUD (soft/hard delete, filters), ML predictions across ticket types and the low-confidence path, retrieved KB text reaching the LLM prompt (different tickets pull different sections), draft + sources saved, edit/save final response, LLM-down and ML-missing and empty-KB failures with recovery, all five field types with validation and runtime-added fields, and the Chroma path (with a stub embedder).

The LLM is stubbed in tests, so the suite needs no Ollama and no model downloads. The frontend is checked by `npm run build` (strict TypeScript).

## 11. Repository layout

```
backend/
  app/            main.py, config.py, models.py, schemas.py, cli.py, seed.py
    routers/      tickets.py, fields.py
    services/     ml.py, rag.py, llm.py, pipeline.py, fields.py
  data/tickets.csv        sample training set (synthetic)
  kb/*.md                 sample knowledge-base documents
  schema.sql              PostgreSQL DDL
  tests/
frontend/src/     App.tsx, api.ts, components/ (TicketForm, TicketDetail, DynamicFields, FieldAdmin, Badges)
docker-compose.yml
```

## 12. Known limitations

- Training data is synthetic; accuracy on real tickets is unmeasured.
- Background drafts use FastAPI `BackgroundTasks` (in-process). For multi-worker production, move to a real queue (Celery/RQ).
- No authentication; add it before exposing beyond a trusted network.
- Schema is created with `create_all`; use Alembic if the schema will evolve.
- The default 3B model is chosen for laptops. Output quality improves noticeably with `llama3.1:8b` if you have the RAM.
