"""Pluggable embedders. nomic-embed-text wants task prefixes on documents and queries."""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.name, self.model, self.host = f"ollama:{model}", model, host.rstrip("/")

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        r = httpx.post(f"{self.host}/api/embed", json={"model": self.model, "input": inputs}, timeout=600)
        r.raise_for_status()
        return r.json()["embeddings"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([f"search_document: {t}" for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"search_query: {text}"])[0]


class FakeEmbedder:
    """Deterministic hashed bag-of-words. For tests only: no network, no model."""
    name = "fake"
    dim = 256

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        from rag.store import tokenize
        for w in tokenize(text):
            if len(w) > 2:
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
