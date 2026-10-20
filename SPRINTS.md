# Noor — Sprint Plan and Definitions of Done

Source: `PRD — Noor: Islamic RAG Assistant`. This file expands its sprint table (Sprints 0–5) and
adds Sprint 6 for the Added Features (F11–F20). Every DoD item is a check you can run: a command
with an expected result, a number to meet, or a file that must exist.

## Corpus (verified 2026-10-19)

- **Location:** `D:\Code\book-reader\public\library\` (the Book Reader app's converted library).
  `D:\Code\book-converter\_out\` is an older, different layout (`_out/<slug>/<book>/<chapter>.json`)
  and is **not** used.
- **Shape:** `<book-id>/<NNN-chapter>.json` = `{id, title, blocks: [{t, text, page?, n?}]}`, plus
  `<book-id>/book.json` (title, author, toc) and a top-level `index.json`.
- **Size:** 12 books, 633 chapter files, 45,360 blocks, ~1.49M words. Sahih al-Bukhari is ~44% of it.
- Noor reads this path in place through `NOOR_LIBRARY` in `.env`. Nothing is copied into this repo.
- The library's `the-clear-quran` and `sahih-al-bukhari` are converted PDFs of the same texts the
  APIs provide with proper verse and hadith numbers. They are skipped by default
  (`NOOR_SKIP_BOOKS`), so search doesn't return the same passage twice.

## Model decisions (2026-10-20)

- Default model is `ollama:qwen2.5:7b`: local and free. Claude (`claude-haiku`, `claude-sonnet`)
  works as soon as `ANTHROPIC_API_KEY` is in `.env`. API billing is separate from the Claude subscription.
- Groq (a free cloud tier) is parked for later. It would be a third provider behind the same
  interface. Ollama stays for embeddings either way.

## Push gate (runs before every push, every sprint)

`python scripts/leak_check.py` must exit 0. It checks:

1. **Ignored:** `git check-ignore` matches `data/`, `data/chroma/`, `data/noor.db`, `.env`, `library/`.
2. **Hook live:** `.git/hooks/pre-commit` is installed and rejects a staged test file
   `library/x/001.json` and a staged file holding a 12-word run taken from the real library.
3. **History clean:** no 12-word run from any library block shows up in `git log -p --all`.
   The check compares the real local library against all of history. Expected matches: 0.
4. **Demo text is ours:** every file under `samples/` passes check 3 too, and is under 3 KB.

If any check fails, nothing gets pushed. Repo: `github.com/NabilPervez/noor` (public). Tags: `sprint-0` … `sprint-6`.

---

## Sprint 0 — Setup (~2 h)

**Tasks**
- 0.1 `CLAUDE.md` (stack, commands, rule: never commit `data/`, `.env` or book text) and `AGENTS.md`.
- 0.2 `.gitignore`: `data/`, `.env`, `library/`, `*.db`, `chroma/`, `.venv/`, caches.
- 0.3 Python 3.11 venv; `pyproject.toml` with a `noor` console script (Typer CLI with stubs).
- 0.4 `.env.example` with `NOOR_LIBRARY`, `NOOR_MODEL`, `ANTHROPIC_API_KEY=` (left empty).
- 0.5 `scripts/pre-commit` hook and `scripts/install_hooks.py`; `scripts/leak_check.py`.
- 0.6 `samples/library/`: 1 fake book, 2 chapters, self-written passages, for tests and the demo.
- 0.7 `ollama pull nomic-embed-text` and one chat model (`llama3.1:8b` or `qwen2.5:7b`).
- 0.8 Repo layout from the PRD: `ingest/ rag/ api/ web/ evals/ governance/ reports/`.

**Definition of Done**
- [x] `noor --help` exits 0 and lists `ingest` and `ask`.
- [x] `ollama list` shows `nomic-embed-text` and one chat model.
- [x] `pytest` exits 0 (smoke test: the package imports and the CLI runs).
- [x] `python scripts/leak_check.py` exits 0.
- [x] Fresh clone into a temp folder: `git grep -nE "sk-ant-[A-Za-z0-9_-]{20,}|ANTHROPIC_API_KEY=[A-Za-z0-9]"` finds nothing,
      and no `*.json` exists outside `samples/` and config.
- [x] `CLAUDE.md`, `AGENTS.md`, `.env.example` exist. Tag `sprint-0` is pushed.

## Sprint 1 — Core RAG (~1 weekend) · F1–F5

**Tasks**
- 1.1 `ingest/reader.py`: walks `<lib>/<book>/*.json` and takes author and title from `book.json`.
  Handles blocks without `page`, list numbers (`n`), and `*md*` markup.
- 1.2 `rag/chunk.py`: packs blocks into 400–800-token chunks. Headings start a new chunk and are
  never stranded at the end of one. Metadata: book, author, chapter, page start and end, block range.
  Stable ID `<book>:<chapter>:<b0>-<b1>`.
- 1.3 `rag/embed.py`: `Embedder` interface, `OllamaEmbedder` (nomic-embed-text) and a `FakeEmbedder` for tests.
- 1.4 `rag/store.py`: Chroma persisted at `data/chroma/`. A manifest keyed on chapter hash lets
  re-ingest skip unchanged chapters (F1).
- 1.5 `rag/retrieve.py`: top-k vector search plus BM25 (rank-bm25), merged with reciprocal-rank fusion.
- 1.6 `rag/providers/`: `LLMProvider` protocol, `ClaudeProvider` (Haiku/Sonnet), `OllamaProvider`.
  Model is picked by `NOOR_MODEL` = `claude-haiku | claude-sonnet | ollama:<model>` (F4).
- 1.7 `rag/answer.py`: refusal gate (best vector similarity below threshold, or no BM25 hit, gives
  "Not found in your library", F3). Prompt requires `[chunk_id]` citations and forbids rulings.
  Citations are checked against the retrieved IDs.
- 1.8 `rag/log.py`: SQLite `data/noor.db` with ts, model, tokens_in, tokens_out, cost_usd,
  latency_ms, chunk_ids, refused. It stores **no** passage text. Prices live in one table in code.
- 1.9 CLI `noor ingest <path>`, `noor ask "<q>"` (numbered citations: book, chapter, page), `noor log`.
- 1.11 `ingest/sources/`: Quran and hadith from the open fawazahmed0 APIs, the same ones
  `quran-reflection`, `hadith-reflection` and `islamic-rag-quran-and-hadith` already use. Files come
  from jsDelivr (`quran-api@1`, `hadith-api@1`), with a raw.githubusercontent.com fallback. Downloads
  are cached in `data/sources/` (git-ignored), then converted into the same block shape as the
  library: Quran = one chapter per surah, each ayah one block with ID `quran:<s>:<a>`; hadith = one
  chapter per section, each hadith one block that keeps its number and grades. Command:
  `noor sources pull quran,bukhari,muslim`. Editions are set in config (default `eng-mustafakhattaba`
  and `ara-quranuthmani`). Citations read "Quran 2:153" and "Sahih Muslim 2999".
- 1.10 Tests: chunking, retrieval, refusal, logging, citation validation. They run on `samples/`
  with `FakeEmbedder` and a fake provider, so CI needs no Ollama and no API key.

**Definition of Done**
- [x] `pytest` exits 0. It covers chunk sizes in [400, 800] tokens (except a chapter's last chunk),
      headings never ending a chunk, stable IDs, metadata fields, the merge order of BM25 plus
      vector results, refusal on an off-topic question, and one log row per ask with no text column.
- [x] `noor ingest $NOOR_LIBRARY` completes for at least 3 real books. Running it again reports
      `0 chapters re-indexed`.
- [x] `noor ask` on 3 questions, one per book, prints an answer with at least 1 numbered citation
      (book · chapter · p.N). Every cited ID is among the retrieved chunks.
- [x] `noor ask "What is the capital of Australia?"` prints `Not found in your library`.
- [x] `NOOR_MODEL=ollama:<model> noor ask …` works with no API key set.
- [~] `sqlite3 data/noor.db "select model,tokens_in,tokens_out,cost_usd,latency_ms,chunk_ids from queries"`
      shows one row per ask. `cost_usd` > 0 for Claude and = 0 for Ollama.
      *Status 2026-10-20: rows are logged for Ollama with cost 0. The Claude row (cost > 0) waits for an
      `ANTHROPIC_API_KEY`; the cost math is unit-tested (`test_cost_math`).*
- [x] `noor sources pull quran,bukhari` writes only under `data/sources/`. `noor ask "What does the
      Quran say about patience?"` cites at least one `quran:<s>:<a>` ayah. A pytest test runs the
      Quran and hadith converters on small self-written fixtures, with no network.
- [x] Leak gate exits 0. Tag `sprint-1` is pushed.

## Sprint 2 — Cost model (~1 evening) · F8

**Tasks**
- 2.1 Prompt caching (`cache_control`) on the system prompt; log `cache_read` and `cache_write` tokens.
- 2.2 Answer cache keyed on normalized question + model + index version, stored in SQLite.
- 2.3 `scripts/cost_report.py`: reads the log and writes `reports/cost.md`.
- 2.4 A fixed 20-question bench run on Haiku, Sonnet and one Ollama model.

**Definition of Done**
- [x] `reports/cost.md` exists with: prices and the date they were pulled from Anthropic's pricing
      page; average tokens in and out; $/query per model; monthly cost at 100, 1k and 10k queries;
      Ollama latency and hardware note.
- [~] Caching savings are shown as before-and-after %, measured from the logs: prompt cache and answer cache each.
      *Status 2026-10-20: the Ollama rows and the answer-cache saving are measured. Claude cost and prompt-cache
      savings are projected from measured token counts until an `ANTHROPIC_API_KEY` exists (see reports/cost.md).*
- [x] Asking the same question twice: the second log row has `cached=1` and `cost_usd=0`.
- [x] `pytest` exits 0, with tests for the cost math and the cache key. Leak gate exits 0. Tag `sprint-2` is pushed.

## Sprint 3 — Evals (~1 weekend)

**Tasks**
- 3.1 `evals/golden.yaml`: 30–50 questions with expected chunk IDs, including 5–10 unanswerable
  questions. It stores IDs and our own question wording, never passage text.
- 3.2 `evals/run.py`: retrieval hit@k, groundedness (LLM judge), refusal accuracy, p50/p95 latency, $/query.
- 3.3 `evals/rubric.md`: go/no-go thresholds of hit@5 ≥ 85%, grounded ≥ 90%, refusal = 100%.
- 3.4 `evals/spotcheck.csv`: human spot-check of 10 answers per model.

**Definition of Done**
- [~] `python -m evals.run --model claude-haiku` (and sonnet, ollama) exits 0.
      *Status 2026-10-20: ollama:qwen2.5:7b run complete (NO-GO on groundedness, 79.4% vs 90%). Claude runs wait
      for an `ANTHROPIC_API_KEY`. The human spot-check in `evals/spotcheck.csv` is waiting for a person.*
- [x] `reports/eval.md` has a scores table per model and a GO or NO-GO line per model against the rubric.
- [x] The golden set has ≥30 questions, and between 5 and 10 of them are unanswerable.
- [x] Leak gate exits 0. It scans `evals/` and `reports/` too. Tag `sprint-3` is pushed.

## Sprint 4 — Governance + UI (~1 weekend) · F6–F7

**Tasks**
- 4.1 `governance/model-card.md`, `governance/nist-ai-rmf.md` (Govern/Map/Measure/Manage, with a
  control for each risk: hallucinated hadith, misattribution, copyright, sectarian bias),
  `governance/data-inventory.md` (each of the 12 books: copyright status, class, storage path).
- 4.2 FastAPI: `POST /ask`, `GET /chunk/{id}` (local only), `GET /models`.
- 4.3 `web/`: React + Vite + Tailwind in the house dark serif-and-gold look. Chat, citation drawer,
  model picker, disclaimer banner.
- 4.4 Threading (F7): a conversation ID and the last N turns go into retrieval and the prompt.

**Definition of Done**
- [ ] All three governance files exist. The NIST file has the 4 functions, ≥4 risks, and each risk has a control.
- [ ] `uvicorn api.main:app` plus `npm run dev` in `web/`: a question gets an answer, clicking a
      citation opens the passage, the model picker changes the `model` in the log row, and the disclaimer is visible.
- [ ] A follow-up question ("what about the second one?") resolves using the earlier turn. There is a test for this.
- [ ] `npm run build` exits 0. `pytest` exits 0 with API tests. Leak gate exits 0. Tag `sprint-4` is pushed.

## Sprint 5 — Ship (~2 h)

**Tasks**
- 5.1 README: what it is, architecture diagram, results (cost and eval numbers), screenshots,
  "use your own books" guide.
- 5.2 Demo GIF recorded against `samples/` only.
- 5.3 GitHub Actions: pytest plus the leak gate on every push.

**Definition of Done**
- [ ] In a fresh clone, run with a timer: venv, install, `noor ingest samples/library`, `noor ask …`.
      It answers in under 10 min, following only the README.
- [ ] The README shows the cost and eval numbers and links `reports/` and `governance/`.
- [ ] The demo GIF shows only `samples/` content. CI is green on `main`. Tag `sprint-5` is pushed.

## Sprint 6 — Added Features · F11–F20

Ordered by priority. Each feature has its own test, and each must not break the Sprint 3 eval GO.

| ID | Task | Done when |
| --- | --- | --- |
| F11 | Book Reader deep link per citation | The link opens `book-reader` at the right `<book>/<chapter>`. A test checks the URL format against the Book Reader route |
| F12 | Arabic term search (sabr, tawakkul…) | A term map is used in query expansion. 10 term queries hit the expected chunks, with hit@5 ≥ 80% |
| F13 | Confidence badge per citation | strong/partial comes from retrieval scores, is shown in the UI, and has unit tests on the threshold |
| F14 | Thumbs up/down that feeds the golden set | A 👎 writes a candidate row to `data/feedback.db` (local). `evals/promote.py` adds it as IDs only |
| F15 | Saved answers notebook, Markdown export | `noor export notes.md` writes saved answers with citations. Notion export is optional |
| F16 | Compare-books mode | `noor compare "<topic>" --books a,b` returns per-book cited columns and refuses per book when that book is weak |
| F17 | Study mode | `noor study <book>/<chapter>` writes a summary plus a 5-question quiz, every item cited |
| F18 | Daily reflection | `noor daily` gives a deterministic passage per date plus a reflection prompt |
| F19 | Glossary of terms | `noor glossary sabr` gives a definition with citations. At least 25 terms |
| F20 | Hadith grade | Grades are already stored from Sprint 1. They're shown next to each hadith citation, and a weak grade gets a warning chip |

**DoD:** each row's "Done when" passes, `pytest` exits 0, the eval is still GO, the leak gate exits 0, and tag `sprint-6` is pushed.
