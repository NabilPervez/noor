"""Settings from the environment and .env (git-ignored)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _list(name: str, default: str) -> list[str]:
    return [s.strip() for s in os.environ.get(name, default).split(",") if s.strip()]


@dataclass
class Settings:
    library: Path | None = field(default_factory=lambda: Path(p) if (p := os.environ.get("NOOR_LIBRARY")) else None)
    data_dir: Path = field(default_factory=lambda: ROOT / os.environ.get("NOOR_DATA_DIR", "data"))
    model: str = field(default_factory=lambda: os.environ.get("NOOR_MODEL", "ollama:qwen2.5:7b"))
    ollama_host: str = field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    embed_model: str = field(default_factory=lambda: os.environ.get("NOOR_EMBED_MODEL", "nomic-embed-text"))
    top_k: int = field(default_factory=lambda: int(os.environ.get("NOOR_TOP_K", "6")))
    # Refuse when the best passage's cosine similarity is below this. Tuned in Sprint 3.
    min_similarity: float = field(default_factory=lambda: float(os.environ.get("NOOR_MIN_SIMILARITY", "0.65")))
    # Library books that duplicate an API source (the API copy has proper verse/hadith numbers).
    skip_books: list[str] = field(default_factory=lambda: _list("NOOR_SKIP_BOOKS", "the-clear-quran,sahih-al-bukhari"))

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "noor.db"

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"
