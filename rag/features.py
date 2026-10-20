"""Sprint 6 "Added Features" (F11-F20) built on the core RAG pipeline."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from ingest.sources import citation
from rag.answer import NOT_FOUND, Answer, extract_citations, is_weak
from rag.log import connect
from rag.providers import LLMProvider
from rag.retrieve import Hit, retrieve
from rag.store import Store
from rag.terms import TERMS, expand, lookup

# --- F13 confidence badge -----------------------------------------------------------------------
STRONG = 0.75   # answerable golden questions: median top similarity 0.78; refusal threshold is 0.65


def confidence(similarity: float) -> str:
    """How well a passage matches the question: 'strong' or 'partial'."""
    return "strong" if similarity >= STRONG else "partial"


# --- F20 hadith grades --------------------------------------------------------------------------
WEAK = re.compile(r"da.?if|daeef|weak|maudu|mawdu|fabricat|munkar|shadh", re.I)


def grade_flag(grades: str | None) -> str | None:
    """'weak' if any listed grade is weak or fabricated, so the UI and CLI can warn."""
    return "weak" if grades and WEAK.search(grades) else None


# --- F11 Book Reader deep link ------------------------------------------------------------------
def book_reader_link(meta: dict, base_url: str | None) -> str | None:
    """Link to the chapter in Book Reader (needs the deep-link handler in docs/book-reader-deeplink.md)."""
    if not base_url or meta.get("kind") != "book":
        return None
    params = {"book": meta["book_id"], "chapter": meta["chapter_id"]}
    if meta.get("block_start") not in (None, ""):
        params["block"] = int(meta["block_start"])
    return f"{base_url.rstrip('/')}/?{urlencode(params)}"


# --- F16 compare books --------------------------------------------------------------------------
COMPARE_SYSTEM = """You summarise what ONE book says about a topic, using only the passages given.
Cite every sentence with the passage ID in square brackets, exactly as given. Two to four sentences.
If the passages do not address the topic, reply with exactly NOT_FOUND. Do not issue religious rulings."""


@dataclass
class BookView:
    book_id: str
    book_title: str
    answer: Answer


def compare(topic: str, books: list[str], store: Store, provider: LLMProvider, *,
            k: int = 4, min_similarity: float = 0.65) -> list[BookView]:
    views = []
    for b in books:
        hits = retrieve(store, expand(topic), k=k, where={"book_id": b})
        title = hits[0].meta.get("book_title", b) if hits else b
        if is_weak(hits, min_similarity):
            views.append(BookView(b, title, Answer(NOT_FOUND, True, hits=hits, reason="no strong passage in this book")))
            continue
        prompt = "\n\n".join(f"[{h.id}]\n{h.text}" for h in hits) + f"\n\nTopic: {topic}"
        g = provider.generate(COMPARE_SYSTEM, prompt)
        text, cited = extract_citations(g.text, [h.id for h in hits])
        by_id = {h.id: h for h in hits}
        if not cited:
            views.append(BookView(b, title, Answer(NOT_FOUND, True, hits=hits, generation=g, reason="no cited answer")))
        else:
            views.append(BookView(b, title, Answer(text, False, [(n + 1, by_id[c]) for n, c in enumerate(cited)], hits, g)))
    return views


# --- F17 study mode -----------------------------------------------------------------------------
STUDY_SYSTEM = """You make study notes from ONE chapter, using only the passages given.
Write:
SUMMARY: 3-5 sentences.
QUIZ: exactly 5 numbered questions, each followed by "Answer:" and a one-sentence answer.
Cite every summary sentence and every answer with a passage ID in square brackets, exactly as given.
Do not issue religious rulings."""


def chapter_hits(store: Store, chapter_key: str, max_chunks: int = 8) -> list[Hit]:
    got = store.col.get(where={"chapter_key": chapter_key}, include=["documents", "metadatas"])
    rows = sorted(zip(got["ids"], got["documents"], got["metadatas"]), key=lambda r: int(r[2].get("block_start") or 0))
    return [Hit(i, d, m, 1.0, 0.0, 0.0) for i, d, m in rows[:max_chunks]]


def study(chapter_key: str, store: Store, provider: LLMProvider) -> Answer:
    hits = chapter_hits(store, chapter_key)
    if not hits:
        return Answer(f"No chapter {chapter_key!r} in the index.", True, reason="unknown chapter")
    prompt = "\n\n".join(f"[{h.id}]\n{h.text}" for h in hits)
    g = provider.generate(STUDY_SYSTEM, prompt)
    text, cited = extract_citations(g.text, [h.id for h in hits])
    by_id = {h.id: h for h in hits}
    return Answer(text, not cited, [(n + 1, by_id[c]) for n, c in enumerate(cited)], hits, g,
                  "" if cited else "study notes had no valid citations")


def quiz_count(text: str) -> int:
    return len(re.findall(r"(?m)^\s*\d+[.)]\s", text.split("QUIZ", 1)[-1]))


# --- F18 daily reflection -----------------------------------------------------------------------
REFLECTIONS = [
    "What is one thing in this passage you could act on today?",
    "Which word or phrase here stays with you, and why?",
    "Where in your week could this passage have changed how you responded?",
    "What would it look like to live this passage for one full day?",
    "Who in your life does this passage make you think of?",
    "What does this passage ask you to let go of?",
    "How does this passage change how you see a difficulty you are facing?",
]


def daily(store: Store, day: date | None = None, kinds: tuple[str, ...] = ("quran", "book")) -> tuple[Hit, str]:
    """The same passage and prompt for everyone on a given date; changes each day."""
    day = day or date.today()
    ids = sorted(i for k in kinds for i in store.col.get(where={"kind": k}, include=[])["ids"])
    if not ids:
        raise ValueError("index is empty")
    seed = int(hashlib.sha256(day.isoformat().encode()).hexdigest(), 16)
    cid = ids[seed % len(ids)]
    got = store.col.get(ids=[cid], include=["documents", "metadatas"])
    return Hit(cid, got["documents"][0], got["metadatas"][0], 1.0, 0.0, 0.0), REFLECTIONS[seed % len(REFLECTIONS)]


# --- F19 glossary -------------------------------------------------------------------------------
def glossary(term: str, store: Store, k: int = 3) -> tuple[tuple[str, str, str] | None, list[Hit]]:
    """(key, english, gloss) plus the library passages that best show the term in use."""
    entry = lookup(term)
    if not entry:
        return None, []
    key, english, _ = entry
    return entry, retrieve(store, f"{key} {english}", k=k)


def glossary_terms() -> list[str]:
    return sorted(TERMS)


# --- F15 notebook and F14 feedback (local SQLite, git-ignored) -----------------------------------
NOTES_SCHEMA = """
create table if not exists notes (id integer primary key, ts text, question text, answer text, citations text);
create table if not exists feedback (id integer primary key, ts text, query_id integer, question text,
                                     vote integer, cited_ids text, comment text);
"""


def _db(path: Path) -> sqlite3.Connection:
    con = connect(path)
    con.executescript(NOTES_SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_note(path: Path, question: str, answer: str, citations: list[dict]) -> int:
    with _db(path) as con:
        return con.execute("insert into notes (ts, question, answer, citations) values (?,?,?,?)",
                           (_now(), question, answer, json.dumps(citations))).lastrowid


def export_notes(path: Path) -> str:
    """The notebook as Markdown, each answer followed by its numbered sources."""
    with _db(path) as con:
        rows = con.execute("select ts, question, answer, citations from notes order by id").fetchall()
    out = ["# Noor notebook", ""]
    for ts, q, a, cites in rows:
        out += [f"## {q}", "", f"*Saved {ts[:10]}*", "", a, ""]
        for c in json.loads(cites):
            out.append(f"{c['n']}. {c['label']} (`{c['id']}`)")
        out.append("")
    return "\n".join(out)


def record_feedback(path: Path, *, query_id: int | None, question: str, vote: int,
                    cited_ids: list[str], comment: str = "") -> int:
    if vote not in (1, -1):
        raise ValueError("vote must be 1 or -1")
    with _db(path) as con:
        return con.execute("insert into feedback (ts, query_id, question, vote, cited_ids, comment) values (?,?,?,?,?,?)",
                           (_now(), query_id, question, vote, json.dumps(cited_ids), comment[:500])).lastrowid


def bad_answers(path: Path) -> list[dict]:
    with _db(path) as con:
        rows = con.execute("select id, question, cited_ids, comment from feedback where vote = -1 order by id").fetchall()
    return [{"feedback_id": i, "question": q, "cited_ids": json.loads(c), "comment": cm} for i, q, c, cm in rows]


def citation_json(n: int, h: Hit, book_reader_url: str | None = None) -> dict:
    m = h.meta
    return {"n": n, "id": h.id, "label": citation(m), "kind": m.get("kind"), "similarity": round(h.similarity, 3),
            "confidence": confidence(h.similarity), "grades": m.get("grades") or None,
            "grade_flag": grade_flag(m.get("grades")), "book_reader_url": book_reader_link(m, book_reader_url)}
