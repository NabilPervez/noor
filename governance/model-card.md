# Model card: Noor

*Last updated 2026-10-20. Applies to tag `sprint-4` and later.*

## What it is

Noor is a retrieval-augmented question-answering assistant over one person's private library of Islamic
books, plus the Quran (The Clear Quran translation) and Sahih al-Bukhari. It finds passages, writes a
short answer from them, and cites every claim. It runs locally; the language model is swappable.

## Intended use

- A reader asking what *their own* books say about a topic, with sources they can open and check.
- Comparing how different books in the library treat a topic.
- Studying a chapter: summaries and review questions drawn from that chapter.

## Out of scope

- **Religious rulings (fatwas).** Noor reports what sources say and attributes it. It does not tell a
  user what is halal, haram or obligatory for them, and it points personal rulings to a qualified scholar.
- Authenticating hadith beyond the grades in the source data.
- Any text not in the ingested library. Noor refuses instead of answering from general knowledge.
- Public or multi-user hosting. The library is copyrighted and stays on the owner's machine.

## System components

| Component | Choice | Notes |
| --- | --- | --- |
| Embeddings | `nomic-embed-text` via Ollama (local) | 768 dimensions, with task prefixes |
| Vector store | ChromaDB, cosine, persisted in `data/chroma/` | git-ignored |
| Keyword search | BM25 (Lucene IDF), diacritic folding, light stemming | merged with reciprocal-rank fusion |
| Generation | `ollama:qwen2.5:7b` (default, local), `claude-haiku-5-5`, `claude-sonnet-5-5` | chosen by `NOOR_MODEL` |
| Guardrails | citation required, citation IDs validated, refusal threshold 0.65, system prompt rules | `rag/answer.py` |

## Data

See `data-inventory.md`. 10 library books, the Quran (6,236 ayahs in 746 chunks) and Sahih al-Bukhari
(7,676 hadith chunks): 9,930 chunks in total. No book text, chunk text, embedding or query log is in
the repository.

## Evaluation

See `reports/eval.md` and `evals/rubric.md`. The golden set has 46 questions (37 answerable, 9
unanswerable, 3 of them Islamic-sounding traps). Retrieval hit@6 is 86.5%. Model-level scores and the
GO / NO-GO call for each model are in the report. Claude has not been evaluated yet (no API key).

## Known limitations

- **Corpus imbalance.** Bukhari is 77% of the chunks and can crowd book passages out of the top results.
- **Vocabulary mismatch.** A question worded differently from the translation can miss. For example,
  "Throne" did not retrieve 2:255, whose translation uses "Seat".
- **Retrieval was tuned on the evaluation set.** The hit rate is optimistic until a held-out set exists.
- **LLM judge.** Groundedness is scored by a model, and a local judge grading its own model is lenient.
  The human spot-check is pending.
- **Local model latency** is about 9–14 s per answer on an RTX 2070.
- **Translations only.** Noor works on English translations. Nuance in the Arabic can be lost.
- **No sect or school balance in the corpus itself.** Noor reflects whatever the owner's library contains.

## Contact

Owner: Nabil Pervez. Repository: github.com/NabilPervez/noor.
