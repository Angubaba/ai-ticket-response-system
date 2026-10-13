from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{BASE_DIR / 'tickets.db'}"

    # ML
    ml_model_path: Path = BASE_DIR / "models" / "solution_model.joblib"
    ml_dataset_path: Path = BASE_DIR / "data" / "tickets.csv"
    ml_min_confidence: float = 0.25

    # RAG
    kb_dir: Path = BASE_DIR / "kb"
    chroma_dir: Path = BASE_DIR / "chroma_store"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    rag_top_k: int = 3
    rag_min_score: float = 0.45  # cosine similarity floor for dense retrieval
    rag_min_score_lexical: float = 0.08  # floor for the TF-IDF fallback retriever

    # LLM (Ollama, runs locally)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout_s: float = 120.0

    cors_origins: str = "http://localhost:5173,http://localhost:3000"


settings = Settings()
