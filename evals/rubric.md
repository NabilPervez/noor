# Noor evaluation rubric

A model is **GO** for daily use only if it meets every gating threshold below on the golden set
(`evals/golden.yaml`: 37 answerable questions, 9 unanswerable). Otherwise it is **NO-GO**, and the
report lists which thresholds failed.

| Metric | What it measures | Threshold | Gating |
| --- | --- | --- | --- |
| Retrieval hit rate (hit@6) | An expected source is among the 6 retrieved passages | ≥ 85% | yes |
| Groundedness | Share of answers whose every claim the judge finds supported by the cited passages | ≥ 90% | yes |
| Refusal on unanswerable | Share of the 9 unanswerable questions answered "Not found in your library" | 100% | yes |
| Answer rate | Share of answerable questions that got an answer (not a refusal) | ≥ 80% | yes |
| Cited the expected source | Share of answers that cite an expected source | report only | no |
| Latency p50 / p95 | End to end, retrieval plus model | report only (PRD: p50 < 5 s on Haiku) | no |
| Cost per query | From the query log | report only | no |

Notes
- Hit rate depends on retrieval, not the model, so it is the same for every model.
- Groundedness is scored by an LLM judge (`evals/run.py`, `JUDGE` prompt). A judge from the same model
  family as the answerer is lenient, so a GO needs the human spot-check (`evals/spotcheck.csv`) to agree
  on at least 9 of 10 sampled answers.
- 100% refusal is strict on purpose: answering an unanswerable religious question means inventing a source.
- The answer-rate threshold is not in the PRD. It was added so that a model can't pass by refusing
  everything.
