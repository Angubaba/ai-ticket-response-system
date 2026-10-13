"""Local RAG retrieval.

Primary:  sentence-transformers (BAAI/bge-small, runs on CPU) + ChromaDB persistent vector store.
Fallback: in-memory TF-IDF cosine retriever, used automatically if the embedding model or ChromaDB
          can't be loaded (e.g. weights not downloaded yet). Everything is local either way.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, asdict
from pathlib import Path

from ..config import settings

log = logging.getLogger(__name__)

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@dataclass
class Chunk:
    text: str
    source: str  # file name
    title: str  # section heading
    score: float = 0.0  # similarity, higher is better

    def public(self) -> dict:
        d = asdict(self)
        d["score"] = round(self.score, 3)
        return d


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """One chunk per '## ' section; the heading is kept in the chunk text for retrieval context."""
    chunks: list[Chunk] = []
    parts = re.split(r"(?m)^##\s+", text)
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        body = body.strip()
        if body:
            chunks.append(Chunk(text=f"{title.strip()}\n{body}", source=source, title=title.strip()))
    return chunks


def load_chunks(kb_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(kb_dir).glob("**/*.md")):
        chunks += chunk_markdown(path.read_text(encoding="utf-8"), path.name)
    return chunks


def _kb_hash(chunks: list[Chunk], model: str) -> str:
    h = hashlib.sha256(model.encode())
    for c in chunks:
        h.update(c.source.encode())
        h.update(c.text.encode())
    return h.hexdigest()


class EmbeddingsUnavailable(RuntimeError):
    pass


class Embedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer

                        self._model = SentenceTransformer(self.model_name)
                    except Exception as e:
                        raise EmbeddingsUnavailable(f"embedding model '{self.model_name}' unavailable: {e}") from e
        return self._model

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        model = self._load()
        if query and "bge" in self.model_name.lower():
            texts = [BGE_QUERY_PREFIX + t for t in texts]
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


class KnowledgeBase:
    def __init__(self, kb_dir: Path | None = None, chroma_dir: Path | None = None, embedder: Embedder | None = None):
        self.kb_dir = Path(kb_dir or settings.kb_dir)
        self.chroma_dir = Path(chroma_dir or settings.chroma_dir)
        self.embedder = embedder or Embedder(settings.embedding_model)
        self.chunks: list[Chunk] = []
        self.backend = "uninitialized"
        self._collection = None
        self._tfidf = None
        self._tfidf_matrix = None
        self._lock = threading.Lock()
        self._ready = False

    # ---------- indexing ----------
    def index(self, force: bool = False) -> int:
        with self._lock:
            self.chunks = load_chunks(self.kb_dir)
            if not self.chunks:
                self.backend = "empty"
                self._ready = True
                return 0
            try:
                self._index_dense(force)
                self.backend = "chroma+embeddings"
            except Exception as e:  # missing weights, chroma failure, no internet on first run...
                log.warning("Dense retrieval unavailable (%s). Falling back to TF-IDF.", e)
                self._index_lexical()
                self.backend = "tfidf-fallback"
            self._ready = True
            return len(self.chunks)

    def _index_dense(self, force: bool) -> None:
        import chromadb

        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        digest = _kb_hash(self.chunks, self.embedder.model_name)
        hash_file = self.chroma_dir / "kb.hash"
        col = client.get_or_create_collection("knowledge_base", metadata={"hnsw:space": "cosine"})

        up_to_date = (
            not force and hash_file.exists() and hash_file.read_text() == digest and col.count() == len(self.chunks)
        )
        if not up_to_date:
            client.delete_collection("knowledge_base")
            col = client.create_collection("knowledge_base", metadata={"hnsw:space": "cosine"})
            embeddings = self.embedder.encode([c.text for c in self.chunks])
            col.add(
                ids=[f"chunk-{i}" for i in range(len(self.chunks))],
                documents=[c.text for c in self.chunks],
                embeddings=embeddings,
                metadatas=[{"source": c.source, "title": c.title} for c in self.chunks],
            )
            hash_file.write_text(digest)
        self._collection = col

    def _index_lexical(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._collection = None
        self._tfidf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self._tfidf_matrix = self._tfidf.fit_transform([c.text for c in self.chunks])

    def ensure_ready(self) -> None:
        if not self._ready:
            self.index()

    # ---------- search ----------
    @property
    def min_score(self) -> float:
        return settings.rag_min_score if self.backend == "chroma+embeddings" else settings.rag_min_score_lexical

    def search(self, query: str, k: int | None = None) -> list[Chunk]:
        """Top-k chunks above the relevance floor, best first. Empty list = KB has nothing relevant."""
        self.ensure_ready()
        k = k or settings.rag_top_k
        if not self.chunks:
            return []
        if self.backend == "chroma+embeddings":
            try:
                return self._search_dense(query, k)
            except Exception as e:
                log.warning("Dense search failed (%s); switching to TF-IDF fallback.", e)
                with self._lock:
                    self._index_lexical()
                    self.backend = "tfidf-fallback"
        return self._search_lexical(query, k)

    def _search_dense(self, query: str, k: int) -> list[Chunk]:
        emb = self.embedder.encode([query], query=True)
        res = self._collection.query(query_embeddings=emb, n_results=min(k, len(self.chunks)))
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            score = 1.0 - float(dist)
            if score >= self.min_score:
                out.append(Chunk(text=doc, source=meta["source"], title=meta["title"], score=score))
        return out

    def _search_lexical(self, query: str, k: int) -> list[Chunk]:
        from sklearn.metrics.pairwise import cosine_similarity

        sims = cosine_similarity(self._tfidf.transform([query]), self._tfidf_matrix)[0]
        order = sims.argsort()[::-1][:k]
        out = []
        for i in order:
            if sims[i] >= self.min_score:
                c = self.chunks[i]
                out.append(Chunk(text=c.text, source=c.source, title=c.title, score=float(sims[i])))
        return out


_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
