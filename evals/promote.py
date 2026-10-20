"""F14: turn thumbs-down answers into golden-set candidates.

  python -m evals.promote            # appends new candidates to evals/candidates.yaml

Each candidate has the question and the chunk IDs the bad answer cited (IDs only, never text) and
`expect: []` for a person to fill in. Move a reviewed candidate into golden.yaml by hand.
"""
from __future__ import annotations

import yaml

from noor.config import ROOT, Settings
from rag.features import bad_answers

CANDIDATES = ROOT / "evals" / "candidates.yaml"


def promote() -> int:
    existing = yaml.safe_load(CANDIDATES.read_text(encoding="utf-8")) if CANDIDATES.exists() else None
    existing = existing or {"candidates": []}
    seen = {c["feedback_id"] for c in existing["candidates"]}
    new = [{"feedback_id": b["feedback_id"], "q": b["question"], "bad_answer_cited": b["cited_ids"],
            "expect": [], "answerable": None, "reviewed": False}
           for b in bad_answers(Settings().db_path) if b["feedback_id"] not in seen]
    existing["candidates"] += new
    CANDIDATES.write_text("# Thumbs-down answers awaiting review. Fill in `expect` / `answerable`, then move\n"
                          "# the entry into golden.yaml. Source IDs only, never passage text.\n"
                          + yaml.safe_dump(existing, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return len(new)


if __name__ == "__main__":
    print(f"{promote()} new candidate(s) -> {CANDIDATES.relative_to(ROOT)}")
