"""Packs a chapter's blocks into retrieval chunks.

Books: 400-800 tokens, split on block boundaries. A heading starts a new chunk and is never
left dangling at the end of one. Quran: consecutive ayahs, 100-350 tokens. Hadith: one hadith
per chunk (split only if it is longer than the max), so every citation is a single hadith.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ingest.reader import Block, Chapter

UNIT_MAX = 200                       # long blocks are cut into sentence groups this size
SENT = re.compile(r"(?<=[.!?؟])\s+")
LIMITS = {"book": (400, 800), "quran": (100, 350), "hadith": (0, 800)}


def tokens(text: str) -> int:
    """Cheap, model-agnostic estimate (~4 characters per token). Used everywhere for consistency."""
    return max(1, round(len(text) / 4))


@dataclass
class Chunk:
    id: str
    text: str
    book_id: str
    book_title: str
    author: str
    chapter_id: str
    chapter_title: str
    kind: str
    block_start: int
    block_end: int
    page_start: int | None
    page_end: int | None
    refs: str = ""                   # "2:153-157" or "6470"
    grades: str = ""

    @property
    def n_tokens(self) -> int:
        return tokens(self.text)

    @property
    def embed_text(self) -> str:
        return f"{self.book_title} - {self.chapter_title}\n{self.text}"

    def metadata(self) -> dict:
        m = {k: v for k, v in self.__dict__.items() if k not in ("id", "text")}
        return {k: ("" if v is None else v) for k, v in m.items()}


def _units(block: Block) -> list[Block]:
    """Split a block longer than UNIT_MAX tokens into sentence groups (same index/page)."""
    if tokens(block.text) <= UNIT_MAX:
        return [block]
    pieces, cur = [], ""
    for sent in SENT.split(block.text):
        while tokens(sent) > UNIT_MAX:          # one enormous sentence: cut on words
            words = sent.split()
            half = max(1, len(words) // 2)
            head, sent = " ".join(words[:half]), " ".join(words[half:])
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(head)
        if cur and tokens(cur + " " + sent) > UNIT_MAX:
            pieces.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        pieces.append(cur)
    return [Block(t=block.t, text=p, index=block.index, page=block.page, n=block.n,
                  ref=block.ref, grades=block.grades) for p in pieces]


def _render(u: Block) -> str:
    if u.is_heading:
        return f"## {u.text}"
    if u.t == "li" and u.n is not None:
        return f"{u.n}. {u.text}"
    if u.t in ("li", "bullet"):
        return f"- {u.text}"
    if u.t == "quote":
        return f"> {u.text}"
    if u.t == "ayah":
        return f"({u.ref}) {u.text}"
    return u.text


def _group(units: list[Block], lo: int, hi: int, per_unit: bool) -> list[list[Block]]:
    groups: list[list[Block]] = []
    cur: list[Block] = []
    for u in units:
        size = _size(cur)
        new_hadith = per_unit and cur and u.ref != cur[-1].ref
        if cur and (new_hadith or _size(cur + [u]) > hi or (u.is_heading and size >= lo)):
            # never end a chunk on a heading: carry trailing headings forward
            carry = []
            while len(cur) > 1 and cur[-1].is_heading:
                carry.insert(0, cur.pop())
            groups.append(cur)
            cur = carry
        cur.append(u)
    if cur:
        if groups and _size(cur) < lo and not per_unit and _size(groups[-1] + cur) <= hi:
            groups[-1].extend(cur)                     # fold a short tail into the previous chunk
        else:
            groups.append(cur)
    return groups


def _size(units: list[Block]) -> int:
    """Token size of the chunk text exactly as it will be rendered."""
    return tokens("\n\n".join(_render(u) for u in units)) if units else 0


def chunk_chapter(ch: Chapter) -> list[Chunk]:
    lo, hi = LIMITS[ch.kind]
    units = [u for b in ch.blocks for u in _units(b)]
    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    for g in _group(units, lo, hi, per_unit=ch.kind == "hadith"):
        b0, b1 = g[0].index, g[-1].index
        pages = [u.page for u in g if u.page is not None]
        if ch.kind == "quran":
            s = ch.chapter_id.lstrip("0") or "0"
            a0, a1 = g[0].ref.split(":")[1], g[-1].ref.split(":")[1]
            refs = f"{s}:{a0}" if a0 == a1 else f"{s}:{a0}-{a1}"
            cid = f"quran:{refs}"
        elif ch.kind == "hadith":
            refs = g[0].ref
            cid = f"{ch.book_id}:{refs}"
        else:
            refs = ""
            cid = f"{ch.book_id}:{ch.chapter_id}:{b0}-{b1}"
        if cid in seen:                                # a block split across several chunks
            seen[cid] += 1
            cid = f"{cid}.{seen[cid]}"
        else:
            seen[cid] = 0
        grades = "; ".join(f"{gr.get('name')}: {gr.get('grade')}" for gr in g[0].grades) if ch.kind == "hadith" else ""
        chunks.append(Chunk(
            id=cid, text="\n\n".join(_render(u) for u in g), book_id=ch.book_id,
            book_title=ch.book_title, author=ch.author, chapter_id=ch.chapter_id,
            chapter_title=ch.chapter_title, kind=ch.kind, block_start=b0, block_end=b1,
            page_start=min(pages) if pages else None, page_end=max(pages) if pages else None,
            refs=refs, grades=grades))
    return chunks
