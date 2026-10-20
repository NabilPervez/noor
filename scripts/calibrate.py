"""Print retrieval similarity for questions the library can and can't answer, to pick
NOOR_MIN_SIMILARITY. Retrieval only: no LLM calls, no cost. Sprint 3 replaces this with the golden set.

  python scripts/calibrate.py
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noor.cli import _store                      # noqa: E402
from noor.config import Settings                 # noqa: E402
from rag.retrieve import retrieve                # noqa: E402

ANSWERABLE = [
    "What does the Quran say about patience?",
    "How should a believer deal with trauma and grief?",
    "What are the proofs of the prophethood of Muhammad?",
    "What does Al-Ghazali say about the heart and happiness?",
    "What happened at the Battle of Badr?",
    "What are the etiquettes of entering the mosque?",
    "What is the meaning of the name Al-Wadud?",
    "How can I control anger?",
    "What did the Prophet say about intentions?",
    "Why do trials and tribulations happen to believers?",
]
UNANSWERABLE = [
    "What is the capital of Australia?",
    "How do I change the oil in a Toyota Corolla?",
    "Who won the 2018 FIFA World Cup?",
    "What is the boiling point of mercury?",
    "Explain how a transistor works.",
    "What is the best recipe for chocolate chip cookies?",
    "How many moons does Jupiter have?",
    "What programming language is Kubernetes written in?",
]


def top(store, q):
    hits = retrieve(store, q, k=6)
    return max((h.similarity for h in hits), default=0.0), hits[0].id if hits else "-"


if __name__ == "__main__":
    store = _store(Settings())
    rows = {}
    for label, qs in (("answerable", ANSWERABLE), ("unanswerable", UNANSWERABLE)):
        print(f"\n{label}")
        rows[label] = []
        for q in qs:
            sim, cid = top(store, q)
            rows[label].append(sim)
            print(f"  {sim:.3f}  {q[:60]:60}  {cid}")
    a, u = rows["answerable"], rows["unanswerable"]
    print(f"\nanswerable   min {min(a):.3f}  median {statistics.median(a):.3f}")
    print(f"unanswerable max {max(u):.3f}  median {statistics.median(u):.3f}")
    print(f"suggested threshold: {(min(a) + max(u)) / 2:.3f}" if min(a) > max(u)
          else "ranges overlap: the LLM's NOT_FOUND check has to catch the rest")
