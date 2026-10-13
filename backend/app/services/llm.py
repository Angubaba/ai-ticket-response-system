"""Thin client for a locally running Ollama server. No cloud calls."""
from __future__ import annotations

import httpx

from ..config import settings


class LLMUnavailable(RuntimeError):
    """Ollama not running, model missing, timed out, or returned garbage."""


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.llm_timeout_s

    def health(self) -> tuple[bool, bool]:
        """(server_reachable, model_pulled)"""
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
            wanted = self.model if ":" in self.model else f"{self.model}:latest"
            return True, any(n == wanted or n == self.model for n in names)
        except Exception:
            return False, False

    def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        except httpx.ConnectError as e:
            raise LLMUnavailable(f"Cannot reach Ollama at {self.base_url}. Is it running? (`ollama serve`)") from e
        except httpx.TimeoutException as e:
            raise LLMUnavailable(f"Ollama timed out after {self.timeout:.0f}s") from e
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"Ollama request failed: {e}") from e

        if r.status_code == 404:
            raise LLMUnavailable(f"Model '{self.model}' not found. Run `ollama pull {self.model}`.")
        if r.status_code >= 400:
            raise LLMUnavailable(f"Ollama returned HTTP {r.status_code}: {r.text[:200]}")
        try:
            text = r.json()["message"]["content"].strip()
        except Exception as e:
            raise LLMUnavailable("Unexpected response format from Ollama") from e
        if not text:
            raise LLMUnavailable("Ollama returned an empty response")
        return text


_client: OllamaClient | None = None


def get_llm_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client
