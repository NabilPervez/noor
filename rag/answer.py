"""Question -> retrieved passages -> cited answer, or a refusal. Every call is logged."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ingest.sources import citation
from rag.log import log_query
from rag.providers import Generation, LLMProvider
from rag.retrieve import Hit, retrieve
from rag.store import Store

NOT_FOUND = "Not found in your library."
SYSTEM = """You are Noor, a research assistant for a personal library of Islamic books, the Quran and hadith.

Rules:
1. Answer ONLY from the numbered passages provided. Do not use outside knowledge, and never invent a verse, hadith, scholar or quotation.
2. Cite every claim with the passage ID in square brackets exactly as given, e.g. [quran:2:153-157] or [the-straight-path:003-part-3:12-19]. Only cite IDs that appear in the passages.
3. If the passages do not answer the question, reply with exactly: NOT_FOUND
4. Do not issue religious rulings (fatwas). You may report what the sources say; for a personal ruling, tell the user to consult a qualified scholar.
5. Be concise: a short answer, then supporting points. Quote briefly when wording matters."""
CITE = re.compile(r"\[([^\[\]]+)\]")


@dataclass
class Answer:
    text: str                              # with [n] citation numbers
    refused: bool
    citations: list[tuple[int, Hit]] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    generation: Generation | None = None
    reason: str = ""


def build_prompt(question: str, hits: list[Hit]) -> str:
    parts = [f"[{h.id}] ({citation(h.meta)})\n{h.text}" for h in hits]
    return "Passages:\n\n" + "\n\n---\n\n".join(parts) + f"\n\nQuestion: {question}"


def extract_citations(text: str, allowed: list[str]) -> tuple[str, list[str]]:
    """Replace [chunk-id] markers with [n]; drop IDs that were not retrieved. Returns (text, cited ids)."""
    order: list[str] = []

    def sub(m: re.Match) -> str:
        nums = []
        for raw in re.split(r"[;,]\s*", m.group(1)):
            cid = resolve(raw.strip(), allowed)
            if cid:
                if cid not in order:
                    order.append(cid)
                nums.append(str(order.index(cid) + 1))
        return f"[{', '.join(nums)}]" if nums else ("" if _looks_like_id(m.group(1)) else m.group(0))

    return CITE.sub(sub, text).strip(), order


QURAN_REF = re.compile(r"^quran:(\d+):(\d+)(?:-(\d+))?$")


def resolve(cid: str, allowed: list[str]) -> str | None:
    """Map a cited ID to a retrieved chunk ID. Models often cite one ayah ("quran:11:11")
    inside a retrieved passage ("quran:11:8-14"); that counts as citing the passage."""
    if cid in allowed:
        return cid
    low = cid.lower()
    for a in allowed:
        if a.lower() == low:
            return a
    m = QURAN_REF.match(low)
    if m:
        s, a0, a1 = int(m[1]), int(m[2]), int(m[3] or m[2])
        for a in allowed:
            r = QURAN_REF.match(a)
            if r and int(r[1]) == s and int(r[2]) <= a0 and a1 <= int(r[3] or r[2]):
                return a
    return None


def _looks_like_id(s: str) -> bool:
    return ":" in s and " " not in s.strip()


def is_weak(hits: list[Hit], min_similarity: float) -> bool:
    return not hits or max(h.similarity for h in hits) < min_similarity


def ask(question: str, store: Store, provider: LLMProvider, db_path: Path, *,
        k: int = 6, min_similarity: float = 0.65) -> Answer:
    t0 = time.perf_counter()
    hits = retrieve(store, question, k=k)
    retrieval_ms = int((time.perf_counter() - t0) * 1000)
    top = max((h.similarity for h in hits), default=0.0)

    if is_weak(hits, min_similarity):
        ans = Answer(NOT_FOUND, True, hits=hits, reason=f"best similarity {top:.2f} < {min_similarity}")
        gen = Generation("", provider.name, 0, 0, 0, 0.0)
    else:
        gen = provider.generate(SYSTEM, build_prompt(question, hits))
        text, cited = extract_citations(gen.text, [h.id for h in hits])
        by_id = {h.id: h for h in hits}
        if "NOT_FOUND" in gen.text and not cited:
            ans = Answer(NOT_FOUND, True, hits=hits, generation=gen, reason="model found no answer in the passages")
        elif not cited:
            ans = Answer(NOT_FOUND, True, hits=hits, generation=gen, reason="answer had no valid citations")
        else:
            ans = Answer(text, False, [(n + 1, by_id[c]) for n, c in enumerate(cited)], hits, gen)

    log_query(db_path, question=question, model=gen.model, tokens_in=gen.tokens_in,
              tokens_out=gen.tokens_out, cost_usd=gen.cost_usd,
              latency_ms=int((time.perf_counter() - t0) * 1000), retrieval_ms=retrieval_ms,
              chunk_ids=[h.id for h in hits], cited_ids=[h.id for _, h in ans.citations],
              top_similarity=top, refused=ans.refused)
    return ans
