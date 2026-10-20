"""F12 check: do Arabic-term questions retrieve passages that use the term or its English meaning?

  python -m evals.terms_eval

Relevance is judged mechanically: a top-k passage counts if it contains the term (any spelling, ignoring
diacritics) or its first English equivalent. Run with and without query expansion.
"""
from __future__ import annotations

from noor.cli import _store
from noor.config import ROOT, Settings
from rag.retrieve import retrieve
from rag.store import fold
from rag.terms import TERMS, expand

QUERIES = {   # self-written; term -> question
    "sabr": "What do my books say about sabr?",
    "tawakkul": "What is tawakkul?",
    "shukr": "How do I practise shukr?",
    "tawbah": "What are the conditions of tawbah?",
    "taqwa": "How is taqwa described?",
    "ikhlas": "Why does ikhlas matter?",
    "hasad": "What is said about hasad?",
    "ghibah": "Why is ghibah forbidden?",
    "qadar": "What is belief in qadar?",
    "dhikr": "What are the benefits of dhikr?",
}


def relevant(text: str, term: str) -> bool:
    spellings, english, _ = TERMS[term]
    t = fold(text)
    return any(fold(s) in t for s in spellings) or english.split()[0] in t


def run(k: int = 5) -> dict:
    store = _store(Settings())
    out = {}
    for mode in ("without expansion", "with expansion"):
        hits_ok = 0
        for term, q in QUERIES.items():
            query = expand(q) if mode == "with expansion" else q
            hits_ok += any(relevant(h.text, term) for h in retrieve(store, query, k=k))
        out[mode] = hits_ok / len(QUERIES)
    return out


if __name__ == "__main__":
    res = run()
    lines = ["# F12: Arabic term search", "", f"{len(QUERIES)} term questions (`evals/terms_eval.py`); hit@5 = a top-5 passage "
             "uses the term or its English meaning.", "", "| Retrieval | hit@5 |", "| --- | --- |"]
    lines += [f"| {m} | {v * 100:.0f}% |" for m, v in res.items()]
    lines += ["", f"Target: ≥ 80% with expansion → **{'met' if res['with expansion'] >= 0.8 else 'not met'}**.", ""]
    (ROOT / "reports" / "terms.md").write_text("\n".join(lines), encoding="utf-8")
    print(res)
