"""Noor HTTP API for the web UI. Local only: it serves passage text, so bind it to 127.0.0.1.

  uvicorn api.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import os
import uuid
from functools import lru_cache

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ingest.sources import citation
from noor.config import Settings
from rag.answer import Answer, ask
from rag.features import citation_json, export_notes, record_feedback, save_note
from rag.providers import CLAUDE_ALIASES, get_provider

app = FastAPI(title="Noor", version="0.4.0")
CONVERSATIONS: dict[str, list[tuple[str, str]]] = {}   # in memory; resets when the server restarts


@lru_cache
def settings() -> Settings:
    return Settings()


@lru_cache
def store():
    from noor.cli import _store
    return _store(settings())


@lru_cache(maxsize=8)
def provider(spec: str):
    return get_provider(spec, settings().ollama_host)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    model: str | None = None
    conversation_id: str | None = None


def cite_json(n: int, h) -> dict:
    m = h.meta
    return {**citation_json(n, h, settings().book_reader_url), "book_id": m.get("book_id"),
            "book_title": m.get("book_title"), "chapter_id": m.get("chapter_id"),
            "chapter_title": m.get("chapter_title"), "page_start": m.get("page_start") or None,
            "refs": m.get("refs") or None}


def answer_json(a: Answer, conversation_id: str) -> dict:
    g = a.generation
    return {"answer": a.text, "refused": a.refused, "reason": a.reason, "cached": a.cached,
            "citations": [cite_json(n, h) for n, h in a.citations],
            "model": g.model if g else None, "tokens_in": g.tokens_in if g else 0,
            "tokens_out": g.tokens_out if g else 0, "cost_usd": g.cost_usd if g else 0.0,
            "latency_ms": g.latency_ms if g else 0, "conversation_id": conversation_id,
            "query_id": a.query_id}


@app.post("/api/ask")
def api_ask(body: AskIn) -> dict:
    s = settings()
    try:
        p = provider(body.model or s.model)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    cid = body.conversation_id or uuid.uuid4().hex
    history = CONVERSATIONS.setdefault(cid, [])
    a = ask(body.question, store(), p, s.db_path, k=s.top_k, min_similarity=s.min_similarity,
            history=list(history), tag="web")
    history.append((body.question, a.text))
    return answer_json(a, cid)


@app.get("/api/chunk/{chunk_id:path}")
def api_chunk(chunk_id: str) -> dict:
    got = store().col.get(ids=[chunk_id], include=["documents", "metadatas"])
    if not got["ids"]:
        raise HTTPException(404, "chunk not found")
    m = got["metadatas"][0]
    return {"id": chunk_id, "text": got["documents"][0], "label": citation(m), "meta": m}


@app.get("/api/models")
def api_models() -> dict:
    s = settings()
    models = []
    try:
        tags = httpx.get(f"{s.ollama_host}/api/tags", timeout=3).json().get("models", [])
        models += [{"id": f"ollama:{t['name']}", "label": f"{t['name']} (local, free)", "available": True}
                   for t in tags if "embed" not in t["name"]]
    except httpx.HTTPError:
        pass
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    models += [{"id": alias, "label": f"{alias.replace('-', ' ').title()} (API)", "available": has_key}
               for alias in CLAUDE_ALIASES]
    return {"default": s.model, "models": models}


class FeedbackIn(BaseModel):
    query_id: int | None = None
    question: str = Field(min_length=1, max_length=2000)
    vote: int = Field(ge=-1, le=1)
    cited_ids: list[str] = []
    comment: str = Field("", max_length=500)


@app.post("/api/feedback")
def api_feedback(body: FeedbackIn) -> dict:
    """F14: thumbs up/down. Thumbs-down rows become golden-set candidates (evals/promote.py)."""
    if body.vote == 0:
        raise HTTPException(422, "vote must be 1 or -1")
    fid = record_feedback(settings().db_path, query_id=body.query_id, question=body.question,
                          vote=body.vote, cited_ids=body.cited_ids, comment=body.comment)
    return {"ok": True, "id": fid}


class NoteIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str
    citations: list[dict] = []


@app.post("/api/notes")
def api_save_note(body: NoteIn) -> dict:
    """F15: save an answer to the local notebook."""
    return {"ok": True, "id": save_note(settings().db_path, body.question, body.answer, body.citations)}


@app.get("/api/notes/export", response_class=PlainTextResponse)
def api_export_notes() -> str:
    return export_notes(settings().db_path)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "chunks": store().count()}
