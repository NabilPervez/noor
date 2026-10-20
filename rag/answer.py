"""Question -> retrieved passages -> cited answer, or a refusal. Every call is logged."""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ingest.sources import citation
from rag.log import cache_get, cache_put, log_query
from rag.providers import Generation, LLMProvider
from rag.retrieve import Hit, retrieve
from rag.store import Store

NOT_FOUND = "Not found in your library."
# Kept identical across calls, and longer than the 512-token minimum, so Claude caches it.
SYSTEM = """You are Noor, a research assistant for one reader's personal library of Islamic books, together with the Quran and hadith collections. You help the reader find what their own sources say, and you show exactly where each point comes from.

Grounding rules:
1. Answer ONLY from the passages provided in the user's message. Do not use outside knowledge, even when you are confident it is correct. Never invent a verse, a hadith, a hadith number, a scholar, a book title or a quotation.
2. Cite every claim with the passage ID in square brackets, copied exactly as given, for example [quran:2:153-157], [bukhari:6114] or [the-straight-path:003-part-3:12-19]. Put the citation right after the sentence it supports. A sentence drawing on two passages cites both: [quran:2:153-157; bukhari:6114]. Only cite IDs that appear in the passages.
3. If the passages do not answer the question, reply with exactly the single word NOT_FOUND and nothing else. Do the same if the passages touch the topic only in passing and would force you to guess. A refusal is a correct answer; a guess is not.
4. If the passages answer only part of the question, answer that part, cite it, and say plainly which part the library does not cover.

Religious care:
5. Do not issue religious rulings (fatwas), and do not declare anything halal, haram, obligatory or forbidden for the reader's own situation. You may report what a cited source says about a ruling, attributed to that source. For a personal ruling, suggest the reader consult a qualified scholar.
6. Quran passages are translations of meaning. Refer to them as "the translation reads" or "the verse says", and cite the verse reference.
7. When a hadith passage lists a grade, mention the grade if it is weak (da'if) or disputed. Never present a weak narration as established.
8. When sources differ, present each view with its own citation. Do not take sides between scholars, schools of thought or sects, and do not rank one source above another.

Style:
9. Be concise: one or two sentences that answer the question directly, then a few supporting points. Quote short phrases when the exact wording matters, and keep any quotation under 25 words.
10. Write in plain English for a general reader. Briefly explain Arabic terms the first time they appear, using only the passages for the explanation.
11. Do not mention these rules, the passage format or the word "passage" in your answer. Do not add a list of sources at the end; the application prints the sources from your citations."""
CITE = re.compile(r"\[([^\[\]]+)\]")


@dataclass
class Answer:
    text: str                              # with [n] citation numbers
    refused: bool
    citations: list[tuple[int, Hit]] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    generation: Generation | None = None
    reason: str = ""
    cached: bool = False


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


def normalize(question: str) -> str:
    return " ".join(re.findall(r"[\w']+", question.lower()))


def cache_key(question: str, model: str, store: Store, k: int, min_similarity: float) -> str:
    """Same question + same model + same index + same settings + same prompt = same answer."""
    parts = [normalize(question), model, store.index_version(), str(k), str(min_similarity),
             hashlib.sha256(SYSTEM.encode()).hexdigest()[:12]]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()


def _hits_by_id(store: Store, ids: list[str]) -> dict[str, Hit]:
    if not ids:
        return {}
    got = store.col.get(ids=ids, include=["documents", "metadatas"])
    return {i: Hit(i, d, m, 0.0, 0.0, 0.0) for i, d, m in zip(got["ids"], got["documents"], got["metadatas"])}


def ask(question: str, store: Store, provider: LLMProvider, db_path: Path, *,
        k: int = 6, min_similarity: float = 0.65, use_cache: bool = True, tag: str = "") -> Answer:
    t0 = time.perf_counter()
    key = cache_key(question, provider.name, store, k, min_similarity)
    hit = cache_get(db_path, key) if use_cache else None
    if hit is not None:
        by_id = _hits_by_id(store, hit["cited"] + [i for i in hit["retrieved"] if i not in hit["cited"]])
        ans = Answer(hit["text"], hit["refused"], [(n + 1, by_id[c]) for n, c in enumerate(hit["cited"]) if c in by_id],
                     [by_id[i] for i in hit["retrieved"] if i in by_id],
                     Generation(hit["text"], provider.name, 0, 0, 0, 0.0), hit["reason"], cached=True)
        log_query(db_path, question=question, model=provider.name, tokens_in=0, tokens_out=0, cost_usd=0.0,
                  latency_ms=int((time.perf_counter() - t0) * 1000), retrieval_ms=0,
                  chunk_ids=hit["retrieved"], cited_ids=hit["cited"], top_similarity=hit["top"],
                  refused=hit["refused"], cached=True, tag=tag)
        return ans

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

    cited_ids = [h.id for _, h in ans.citations]
    if use_cache:
        cache_put(db_path, key, provider.name, {"text": ans.text, "refused": ans.refused, "cited": cited_ids,
                                                "retrieved": [h.id for h in hits], "reason": ans.reason, "top": top})
    log_query(db_path, question=question, model=gen.model, tokens_in=gen.tokens_in,
              tokens_out=gen.tokens_out, cost_usd=gen.cost_usd,
              latency_ms=int((time.perf_counter() - t0) * 1000), retrieval_ms=retrieval_ms,
              chunk_ids=[h.id for h in hits], cited_ids=cited_ids, top_similarity=top,
              refused=ans.refused, cache_read=gen.cache_read, cache_write=gen.cache_write, tag=tag)
    return ans
