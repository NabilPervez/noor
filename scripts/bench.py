"""Cost bench: run the 20 bench questions on a model, twice.

Pass 1 ("bench-cold") clears this model's answer cache first, so every question calls the model.
Pass 2 ("bench-repeat") asks the same questions again and should be served by the answer cache.
Rows go to the normal query log (data/noor.db) with those tags; scripts/cost_report.py reads them.

  python scripts/bench.py --model ollama:qwen2.5:7b
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noor.cli import _store                       # noqa: E402
from noor.config import Settings                  # noqa: E402
from rag.answer import ask                        # noqa: E402
from rag.log import connect                       # noqa: E402
from rag.providers import get_provider            # noqa: E402


def questions() -> list[str]:
    lines = (ROOT / "evals" / "bench.txt").read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    s = Settings()
    provider = get_provider(args.model or s.model, s.ollama_host)
    store = _store(s)
    with connect(s.db_path) as con:
        con.execute("delete from answer_cache where model = ?", (provider.name,))
        con.execute("delete from queries where model = ? and tag like 'bench-%'", (provider.name,))
    for tag in ("bench-cold", "bench-repeat"):
        for i, q in enumerate(questions(), 1):
            a = ask(q, store, provider, s.db_path, k=s.top_k, min_similarity=s.min_similarity, tag=tag)
            state = "cache" if a.cached else ("refused" if a.refused else f"{len(a.citations)} cites")
            print(f"{tag:12} {i:2}/20  {state:8}  {q[:60]}", flush=True)
    rows = sqlite3.connect(s.db_path).execute(
        "select tag, count(*), avg(latency_ms), sum(cached) from queries where model=? and tag like 'bench-%' group by tag",
        (provider.name,)).fetchall()
    for r in rows:
        print(r)
