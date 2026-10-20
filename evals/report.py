"""Turn data/evals/*.json into reports/eval.md and a spot-check sheet. Numbers and IDs only.

  python -m evals.report
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date

from noor.config import ROOT, Settings

THRESHOLDS = {"hit_rate": 0.85, "grounded_rate": 0.90, "refusal_rate_unanswerable": 1.0, "answered_rate": 0.80}
LABELS = {"hit_rate": "Retrieval hit@k", "grounded_rate": "Groundedness (judge)",
          "refusal_rate_unanswerable": "Refusal on unanswerable", "answered_rate": "Answer rate"}


def verdict(s: dict) -> tuple[str, list[str]]:
    fails = [LABELS[k] for k, t in THRESHOLDS.items() if s.get(k, 0) < t - 1e-9]
    return ("GO" if not fails else "NO-GO"), fails


def main() -> None:
    d = Settings().data_dir / "evals"
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]
    model_runs = [r for r in runs if r["model"] != "retrieval-only"]
    if not model_runs:
        raise SystemExit("No model runs. Run: python -m evals.run --model <model>")
    first = model_runs[0]
    n_ans = first["summary"]["answerable"]
    out = ["# Noor evaluation report", "",
           f"Generated {date.today().isoformat()} by `evals/report.py`. Golden set: {first['summary']['n']} questions "
           f"({n_ans} answerable, {first['summary']['unanswerable']} unanswerable) in `evals/golden.yaml`; "
           f"rubric in `evals/rubric.md`. Retrieval k = {first['k']}, refusal threshold = {first['min_similarity']}.", "",
           "## Scores and recommendation", "",
           "| Metric | Threshold | " + " | ".join(r["model"] for r in model_runs) + " |",
           "| --- | --- | " + " | ".join("---" for _ in model_runs) + " |"]

    def row(label, key, fmt, thr=""):
        out.append(f"| {label} | {thr} | " + " | ".join(fmt(r["summary"].get(key, 0)) for r in model_runs) + " |")

    pct = lambda x: f"{x * 100:.1f}%"
    row("Retrieval hit@k", "hit_rate", pct, "≥ 85%")
    row("Groundedness (LLM judge)", "grounded_rate", pct, "≥ 90%")
    row("Refusal on unanswerable", "refusal_rate_unanswerable", pct, "100%")
    row("Answer rate (answerable)", "answered_rate", pct, "≥ 80%")
    row("Cited an expected source", "cited_expected_rate", pct)
    row("Latency p50", "latency_p50_ms", lambda x: f"{x / 1000:.1f} s")
    row("Latency p95", "latency_p95_ms", lambda x: f"{x / 1000:.1f} s")
    row("Cost per query", "cost_per_query", lambda x: "$0" if x == 0 else f"${x:.6f}")
    out.append("| **Recommendation** | | " + " | ".join(f"**{verdict(r['summary'])[0]}**" for r in model_runs) + " |")
    out.append("")
    for r in model_runs:
        v, fails = verdict(r["summary"])
        judge = r.get("judge", r["model"])
        out.append(f"- **{r['model']}: {v}.** " + (f"Fails: {', '.join(fails)}. " if fails else "Meets every gating threshold. ")
                   + f"Judge: {judge}" + (" (same model as the answerer, so groundedness is likely lenient)." if judge == r["model"] else "."))
    out += ["- **Claude Haiku / Sonnet: not run yet.** There is no `ANTHROPIC_API_KEY`. Run "
            "`python -m evals.run --model claude-haiku --judge claude-sonnet`, then `python -m evals.report`.", "",
            "## Caveats", "",
            "- Retrieval was tuned on this same golden set (diacritic folding and light stemming in the keyword "
            "index, raising hit@6 from 81.1% to 86.5%), so the hit rate is optimistic. A held-out set is the next step.",
            "- Two labels were widened after inspecting misses, each with a reason in `golden.yaml`: b05 (the "
            "paired teacher/student chapters) and h01 (Bukhari repeats the intentions hadith seven times).",
            "- Groundedness comes from an LLM judge. The human spot-check in `evals/spotcheck.csv` is "
            "still to be filled in by a person.", "",
            "## Per question", "",
            "| ID | Question | Retrieval hit | " + " | ".join(r["model"] for r in model_runs) + " |",
            "| --- | --- | --- | " + " | ".join("---" for _ in model_runs) + " |"]
    by_model = [{q["id"]: q for q in r["questions"]} for r in model_runs]
    for q in first["questions"]:
        cells = []
        for bm in by_model:
            x = bm[q["id"]]
            if x["refused"]:
                cells.append("refused ✓" if not x["answerable"] else "refused ✗")
            else:
                ok = "✓" if (x["answerable"] and x.get("grounded")) else "✗"
                cells.append(f"answered {ok}" + ("" if x["answerable"] else " (should refuse)")
                             + ("" if x.get("grounded") in (True, None) or not x["answerable"] else " ungrounded"))
        hit = "-" if q["hit"] is None else ("✓" if q["hit"] else "✗")
        out.append(f"| {q['id']} | {q['q']} | {hit} | " + " | ".join(cells) + " |")
    out.append("")
    (ROOT / "reports" / "eval.md").write_text("\n".join(out), encoding="utf-8")

    sheet = ROOT / "evals" / "spotcheck.csv"
    if not sheet.exists():                      # never overwrite a human's marks
        answered = [q for q in first["questions"] if not q["refused"]]
        pick = sorted(random.Random(7).sample(answered, min(10, len(answered))), key=lambda q: q["id"])
        with sheet.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "model", "judge_grounded", "human_grounded (y/n)", "notes"])
            for q in pick:
                w.writerow([q["id"], first["model"], q.get("grounded"), "", ""])
    print("wrote reports/eval.md")


if __name__ == "__main__":
    main()
