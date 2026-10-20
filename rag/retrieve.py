"""Hybrid retrieval: vector top-n + BM25 top-n, merged with reciprocal-rank fusion (RRF)."""
from __future__ import annotations

from dataclasses import dataclass

from rag.store import Store, tokenize

RRF_K = 60


@dataclass
class Hit:
    id: str
    text: str
    meta: dict
    similarity: float     # cosine similarity between question and chunk
    bm25: float           # BM25 score (0 if keyword search did not find it)
    score: float          # fused RRF score, used for ordering


def rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def retrieve(store: Store, question: str, k: int = 6, pool: int = 30, where: dict | None = None) -> list[Hit]:
    """`where` filters by chunk metadata, e.g. {"book_id": "the-straight-path"} (F16 compare)."""
    n = store.count()
    if n == 0:
        return []
    qv = store.embedder.embed_query(question)
    res = store.col.query(query_embeddings=[qv], n_results=min(pool, n), where=where,
                          include=["documents", "metadatas", "distances"])
    vec_ids = res["ids"][0]
    sims = {i: 1.0 - d for i, d in zip(vec_ids, res["distances"][0])}
    docs = {i: (doc, m) for i, doc, m in zip(vec_ids, res["documents"][0], res["metadatas"][0])}

    idx = store.bm25()
    bm_scores: dict[str, float] = {}
    q = tokenize(question)
    if idx["bm25"] is not None and q:
        raw = idx["bm25"].get_scores(q)
        rows = range(len(raw))
        if where:      # rank inside the filter, not the whole corpus
            allowed = set(store.col.get(where=where, include=[])["ids"])
            rows = [i for i in rows if idx["ids"][i] in allowed]
        top = sorted(rows, key=lambda i: raw[i], reverse=True)[:pool]
        bm_scores = {idx["ids"][i]: float(raw[i]) for i in top if raw[i] > 0}

    fused = rrf([vec_ids, sorted(bm_scores, key=bm_scores.get, reverse=True)])
    best = sorted(fused, key=fused.get, reverse=True)[:k]
    missing = [i for i in best if i not in docs]
    if missing:   # BM25-only hits: fetch text and compute a real similarity for the refusal gate
        got = store.col.get(ids=missing, include=["documents", "metadatas", "embeddings"])
        for i, d, m, e in zip(got["ids"], got["documents"], got["metadatas"], got["embeddings"]):
            docs[i] = (d, m)
            sims[i] = _cos(qv, e)
    return [Hit(id=i, text=docs[i][0], meta=docs[i][1], similarity=sims.get(i, 0.0),
                bm25=bm_scores.get(i, 0.0), score=fused[i]) for i in best]


def _cos(a, b) -> float:
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return sum(x * y for x, y in zip(a, b)) / (na * nb or 1.0)
