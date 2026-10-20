"""Chroma vector store + BM25 index + per-chapter manifest, all under data/ (git-ignored)."""
from __future__ import annotations

import hashlib
import json
import math
import pickle
import re
import unicodedata
from pathlib import Path
from typing import Callable, Iterable

import chromadb
from rank_bm25 import BM25Okapi

from ingest.reader import Chapter
from rag.chunk import chunk_chapter
from rag.embed import Embedder

STOP = set("a an and are as at be by for from has have he her his i in is it its of on or she "
           "that the their them they this to was were what when where which who will with you your "
           "does do did about how why my me we our us say says".split())
BATCH = 64


def fold(text: str) -> str:
    """Lowercase and strip diacritics, so "al-Wadūd" and "Al-Wadud" match ("wadud", not "wad" + "d")."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).replace("’", "'")


SUFFIXES = ("ings", "ing", "edly", "ed", "ies", "es", "s", "ly")


def stem(w: str) -> str:
    """Light suffix stripping so intention/intentions and love/loving meet. Short words are left alone."""
    if len(w) <= 3 or w.endswith("ss"):
        return w
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)] + ("y" if suf == "ies" else "")
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", fold(text).replace("'", ""))
    return [stem(w) for w in words if w not in STOP and len(w) > 1]


class BM25(BM25Okapi):
    """BM25 with the Lucene IDF, log(1 + (N - n + .5) / (n + .5)), which is never zero or negative.
    Plain Okapi IDF gives a word that appears in half the documents zero weight."""

    def _calc_idf(self, nd):
        for word, freq in nd.items():
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


class Store:
    def __init__(self, data_dir: Path, embedder: Embedder):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        client = chromadb.PersistentClient(path=str(self.data_dir / "chroma"),
                                           settings=chromadb.Settings(anonymized_telemetry=False))
        name = _safe(embedder.name)
        self.col = client.get_or_create_collection(f"noor-{name}", metadata={"hnsw:space": "cosine"})
        self.manifest_path = self.data_dir / f"manifest-{name}.json"
        self.bm25_path = self.data_dir / f"bm25-{name}.pkl"
        self.manifest = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {}
        self._bm25 = None

    def ingest(self, chapters: Iterable[Chapter], progress: Callable[[str], None] = lambda s: None) -> dict:
        """Index chapters whose content hash changed. Returns counts."""
        stats = {"chapters": 0, "reindexed": 0, "chunks": 0}
        for ch in chapters:
            stats["chapters"] += 1
            h = ch.hash
            if self.manifest.get(ch.key) == h:
                continue
            self.col.delete(where={"chapter_key": ch.key})
            chunks = chunk_chapter(ch)
            for i in range(0, len(chunks), BATCH):
                part = chunks[i:i + BATCH]
                self.col.add(ids=[c.id for c in part], documents=[c.text for c in part],
                             embeddings=self.embedder.embed_documents([c.embed_text for c in part]),
                             metadatas=[{**c.metadata(), "chapter_key": ch.key} for c in part])
            self.manifest[ch.key] = h
            self._save_manifest()
            stats["reindexed"] += 1
            stats["chunks"] += len(chunks)
            progress(f"  {ch.key}: {len(chunks)} chunks")
        if stats["reindexed"]:
            self.build_bm25()
        return stats

    def _save_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, indent=0))

    def build_bm25(self) -> int:
        got = self.col.get(include=["documents", "metadatas"])
        corpus = [tokenize(f"{m.get('book_title', '')} {m.get('chapter_title', '')} {d}")
                  for d, m in zip(got["documents"], got["metadatas"])]
        with open(self.bm25_path, "wb") as f:
            pickle.dump({"ids": got["ids"], "bm25": BM25(corpus) if corpus else None}, f)
        self._bm25 = None
        return len(got["ids"])

    def bm25(self) -> dict:
        if self._bm25 is None:
            if not self.bm25_path.exists():
                self.build_bm25()
            with open(self.bm25_path, "rb") as f:
                self._bm25 = pickle.load(f)
        return self._bm25

    def index_version(self) -> str:
        """Changes whenever any chapter is added, changed or removed (keys the answer cache)."""
        return hashlib.sha256(json.dumps(self.manifest, sort_keys=True).encode()).hexdigest()[:16]

    def count(self) -> int:
        return self.col.count()


def _safe(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)
