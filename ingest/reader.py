"""Reads the Book Reader / Book Converter library: <lib>/<book>/<NNN-chapter>.json."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class Block:
    t: str                   # p h2 h3 quote li bullet (books); ayah / hadith (API sources)
    text: str
    index: int               # position in the chapter
    page: int | None = None
    n: int | None = None     # list-item number
    ref: str | None = None   # "2:153" for an ayah, "6470" for a hadith
    grades: list = field(default_factory=list)

    @property
    def is_heading(self) -> bool:
        return self.t in ("h2", "h3")


@dataclass
class Chapter:
    book_id: str
    book_title: str
    author: str
    chapter_id: str
    chapter_title: str
    blocks: list[Block]
    kind: str = "book"       # book | quran | hadith

    @property
    def key(self) -> str:
        return f"{self.book_id}/{self.chapter_id}"

    @property
    def hash(self) -> str:
        h = hashlib.sha256()
        for b in self.blocks:
            h.update(f"{b.t}\x00{b.page}\x00{b.text}\x01".encode("utf-8"))
        return h.hexdigest()[:16]


def read_library(root: Path, skip: list[str] | None = None) -> Iterator[Chapter]:
    skip = set(skip or [])
    for book_dir in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        if book_dir.name in skip:
            continue
        meta_path = book_dir / "book.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        title = meta.get("title") or book_dir.name
        author = meta.get("author") or ""
        for ch_path in sorted(book_dir.glob("*.json")):
            if ch_path.name == "book.json":
                continue
            data = json.loads(ch_path.read_text(encoding="utf-8"))
            blocks = [Block(t=b.get("t", "p"), text=clean(b.get("text", "")), index=i,
                            page=b.get("page"), n=b.get("n"))
                      for i, b in enumerate(data.get("blocks", []))]
            blocks = [b for b in blocks if b.text]
            yield Chapter(book_id=book_dir.name, book_title=title, author=author,
                          chapter_id=data.get("id") or ch_path.stem,
                          chapter_title=data.get("title") or ch_path.stem, blocks=blocks)


def clean(text: str) -> str:
    """Drop the reader's *italic* / **bold** markers; keep the words."""
    return text.replace("**", "").replace("*", "").strip()
