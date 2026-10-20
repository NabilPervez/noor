# Noor — instructions for Claude Code

Noor is a local-first Islamic RAG assistant. It answers questions from a personal library of
Islamic books plus the Quran and hadith, and cites a source chunk for every claim.
The PRD and the sprint plan live in `SPRINTS.md`.

## The one rule

**Never commit book text.** That means no `data/`, no `.env`, no `library/`, no chunk text, no
embeddings, no query logs and no Quran or hadith API downloads. The library is copyrighted and
stays on this machine. Demo and test text lives in `samples/` and must be self-written.
Before every push, run `python scripts/leak_check.py`. If it fails, do not push.

## Stack

Python 3.11+ (3.12 on this PC), Typer CLI, FastAPI, ChromaDB, Ollama (`nomic-embed-text`),
Anthropic SDK, rank-bm25, SQLite, pytest. Front end (Sprint 4): React + Vite + Tailwind.

## Commands

```
python -m venv .venv && .venv/Scripts/activate      # Windows; source .venv/bin/activate elsewhere
pip install -e ".[dev]"
python scripts/install_hooks.py                      # installs the pre-commit leak hook
noor --help
noor ingest <library path>                           # Sprint 1
noor sources pull quran,bukhari                      # Sprint 1
noor ask "question"                                  # Sprint 1
pytest
python scripts/leak_check.py                         # before every push
```

## Layout

- `noor/cli.py`: CLI entry point
- `ingest/`: reads the Book Converter / Book Reader library and the Quran/hadith APIs
- `rag/`: chunk, embed, store, retrieve, providers, answer, log
- `api/`, `web/`: Sprint 4
- `evals/`, `reports/`, `governance/`: Sprints 2–4
- `samples/library/`: self-written fake book used by tests and the demo
- `data/`: git-ignored. Chroma, the SQLite log and API caches go here

## Library format

`<lib>/<book-id>/book.json` (title, author, toc) and `<lib>/<book-id>/<NNN-chapter>.json` =
`{id, title, blocks: [{t, text, page?, n?}]}`. `t` is one of `p h2 h3 quote li bullet`.
The real library is at `D:\Code\book-reader\public\library`. Set it with `NOOR_LIBRARY` in `.env`.

## Guardrails

Every answer cites chunk IDs, and those IDs must have been retrieved. Noor refuses with
"Not found in your library" when retrieval is weak. It never issues rulings (fatwas).
