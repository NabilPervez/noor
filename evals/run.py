"""Run the golden set against a model and write the results.

  python -m evals.run --model ollama:qwen2.5:7b            # full: retrieval + answers + judge
  python -m evals.run --retrieval-only                     # hit@k only, no LLM, seconds

Per-question results (including answer text) go to data/evals/<model>.json (git-ignored).
evals/report.py turns every results file into reports/eval.md (numbers and IDs only).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path

import yaml

from noor.cli import _store
from noor.config import ROOT, Settings
from rag.answer import ask, retrieval_query
from rag.providers import get_provider
from rag.retrieve import Hit, retrieve

GOLDEN = ROOT / "evals" / "golden.yaml"
QREF = re.compile(r"^quran:(\d+):(\d+)(?:-(\d+))?")

JUDGE = """You check whether an answer is supported by its sources. You are strict.

Sources:
{sources}

Answer:
{answer}

Is every factual claim in the answer supported by the sources above? Ignore citation numbers and
style. Reply with JSON only: {{"grounded": true or false, "unsupported": "<the first unsupported claim, or empty>"}}"""


def load_golden() -> list[dict]:
    qs = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))["questions"]
    for q in qs:
        q.setdefault("answerable", True)
        q.setdefault("expect", [])
    return qs


def matches(hit_id: str, meta: dict, expect: str) -> bool:
    """Does a retrieved chunk satisfy one expected-source entry?"""
    if expect.startswith("quran:"):
        m, h = QREF.match(expect), QREF.match(hit_id)
        if not (m and h) or m[1] != h[1]:
            return False
        a = int(m[2])
        return int(h[2]) <= a <= int(h[3] or h[2])
    if "/" in expect:
        return meta.get("chapter_key", "").startswith(expect)
    return hit_id == expect or hit_id.startswith(expect + ".")


def is_hit(hits: list[Hit], expect: list[str]) -> bool:
    return any(matches(h.id, h.meta, e) for h in hits for e in expect)


def judge(provider, answer: str, hits: list[Hit]) -> tuple[bool | None, str]:
    sources = "\n\n".join(f"[{i}] {h.text}" for i, h in enumerate(hits, 1))
    g = provider.generate("You are a careful fact-checker. Reply with JSON only.",
                          JUDGE.format(sources=sources, answer=answer), json_mode=True)
    m = re.search(r"\{.*\}", g.text, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
        return bool(d.get("grounded")), str(d.get("unsupported", ""))[:200]
    except ValueError:
        return None, "judge reply was not JSON"


def run(model: str | None, judge_model: str | None, retrieval_only: bool, k: int) -> dict:
    s = Settings()
    store = _store(s)
    qs = load_golden()
    out = {"model": "retrieval-only" if retrieval_only else (model or s.model), "k": k,
           "min_similarity": s.min_similarity, "index_version": store.index_version(),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "questions": []}
    provider = None if retrieval_only else get_provider(model or s.model, s.ollama_host)
    judge_p = None if retrieval_only else get_provider(judge_model or model or s.model, s.ollama_host)
    if judge_p:
        out["judge"] = judge_p.name
    for i, q in enumerate(qs, 1):
        t0 = time.perf_counter()
        hits = retrieve(store, retrieval_query(q["q"], None), k=k)   # same query as production (F12 expansion)
        row = {"id": q["id"], "q": q["q"], "answerable": q["answerable"],
               "retrieved": [h.id for h in hits],
               "top_similarity": round(max((h.similarity for h in hits), default=0), 4),
               "hit": is_hit(hits, q["expect"]) if q["answerable"] else None,
               "retrieval_ms": int((time.perf_counter() - t0) * 1000)}
        if provider:
            a = ask(q["q"], store, provider, s.db_path, k=k, min_similarity=s.min_similarity,
                    use_cache=False, tag="eval")
            cited = [h for _, h in a.citations]
            row.update(refused=a.refused, answer=a.text, cited=[h.id for h in cited],
                       cited_expected=is_hit(cited, q["expect"]) if q["answerable"] else None,
                       latency_ms=(a.generation.latency_ms if a.generation else 0) + row["retrieval_ms"],
                       cost_usd=a.generation.cost_usd if a.generation else 0.0,
                       tokens_in=a.generation.tokens_in if a.generation else 0,
                       tokens_out=a.generation.tokens_out if a.generation else 0)
            if not a.refused:
                row["grounded"], row["unsupported"] = judge(judge_p, a.text, cited)
        out["questions"].append(row)
        state = "" if not provider else (" refused" if row["refused"] else f" grounded={row.get('grounded')}")
        print(f"{i:2}/{len(qs)} {q['id']} hit={row['hit']}{state}", flush=True)
    out["summary"] = summarize(out["questions"])
    return out


def summarize(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    s = {"n": len(rows), "answerable": len(ans), "unanswerable": len(una),
         "hit_rate": sum(r["hit"] for r in ans) / len(ans)}
    if "refused" in rows[0]:
        answered = [r for r in ans if not r["refused"]]
        judged = [r for r in answered if r.get("grounded") is not None]
        lat = sorted(r["latency_ms"] for r in rows)
        s.update(
            answered_rate=len(answered) / len(ans),
            refusal_rate_unanswerable=sum(r["refused"] for r in una) / len(una),
            false_refusals=len(ans) - len(answered),
            grounded_rate=(sum(r["grounded"] for r in judged) / len(judged)) if judged else 0.0,
            cited_expected_rate=(sum(bool(r["cited_expected"]) for r in answered) / len(answered)) if answered else 0.0,
            latency_p50_ms=lat[len(lat) // 2], latency_p95_ms=lat[min(len(lat) - 1, int(0.95 * (len(lat) - 1) + 0.5))],
            cost_per_query=statistics.mean(r["cost_usd"] for r in rows),
            avg_tokens_in=statistics.mean(r["tokens_in"] for r in rows if r["tokens_in"]) if any(r["tokens_in"] for r in rows) else 0,
        )
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--judge", help="Model for the groundedness judge (default: same as --model)")
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("-k", type=int, default=Settings().top_k)
    a = ap.parse_args()
    res = run(a.model, a.judge, a.retrieval_only, a.k)
    d = Settings().data_dir / "evals"
    d.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", res["model"])
    (d / f"{name}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res["summary"], indent=1))
