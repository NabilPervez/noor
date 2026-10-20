# AGENTS.md

All agents follow `CLAUDE.md`. In short:

- Never commit `data/`, `.env`, `library/`, chunk text, embeddings, query logs or API downloads.
- Run `python scripts/leak_check.py` before any push. If it fails, stop.
- Run `pytest` before any commit. Tests use only `samples/`, a fake embedder and a fake LLM.
- Work sprint by sprint from `SPRINTS.md`. Each sprint ends with a `sprint-N` tag.
