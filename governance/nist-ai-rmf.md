# NIST AI RMF mapping

*Last updated 2026-10-20.* Maps Noor to the four functions of the NIST AI Risk Management Framework
(AI RMF 1.0): **Govern, Map, Measure, Manage**. Every control names the file that implements it, so each
one can be checked.

## Govern: policies, roles, accountability

| Item | How Noor does it |
| --- | --- |
| Accountable owner | Nabil Pervez, sole owner and user (`model-card.md`) |
| Acceptable-use policy | Out-of-scope uses, including "no fatwas", in `model-card.md` and enforced in the system prompt (`rag/answer.py`) |
| Data policy | Copyrighted text never leaves the machine: `data-inventory.md`, `.gitignore`, `scripts/leak_check.py` |
| Change control | Work in sprints with testable Definitions of Done (`SPRINTS.md`); each sprint is tagged; tests and the leak gate run before every push |
| Documentation | Model card, data inventory, this mapping, eval rubric and reports, all versioned in the repo |

## Map: context and risks

**Context.** Single user, personal study, private copyrighted corpus, religious subject matter where a
wrong attribution is a serious error, not a cosmetic one.

| ID | Risk | Likelihood before controls | Impact |
| --- | --- | --- | --- |
| R1 | **Hallucinated hadith or verse**: the model invents a narration, a number or a quotation | High for unguarded LLMs | Severe: false religious content |
| R2 | **Misattribution**: a real passage credited to the wrong book, scholar or hadith number | Medium | High |
| R3 | **Copyright leak**: book text published through the repo, logs or demos | Medium (the sibling `book-reader` repo already has this problem) | High: legal and ethical |
| R4 | **Sectarian or school bias**: one view presented as the only view, or the model taking sides | Medium | High |
| R5 | **Unauthorised rulings**: the assistant answers "is X haram for me?" as a mufti would | Medium | High |
| R6 | **Weak narrations presented as sound** | Medium | High |
| R7 | **Over-trust in the tool**: the user treats answers as authoritative without opening sources | Medium | Medium |
| R8 | **Cost overrun** on paid APIs | Low | Low–Medium |

## Measure: how each risk is tested

| Risk | Metric | Where | Current result |
| --- | --- | --- | --- |
| R1 | Groundedness (LLM judge + human spot-check); refusal on unanswerable and trap questions (u07–u09) | `evals/run.py`, `reports/eval.md` | see report |
| R1, R2 | Citation validity: every cited ID must be a retrieved chunk (unit-tested) | `tests/test_answer.py` | enforced in code |
| R2 | "Cited an expected source" rate on the golden set | `reports/eval.md` | see report |
| R3 | Leak gate: 12-word-run scan of staged files and full history against 1.36M runs of library text | `scripts/leak_check.py` | 0 matches at every push |
| R4 | Not yet measured. Planned: golden questions where sources differ, to check that each view is cited and none is preferred | `evals/golden.yaml` (to add) | gap |
| R5 | Planned: golden questions asking for personal rulings; the expected behaviour is attribution plus a referral | to add | gap |
| R6 | Hadith grades kept from the source data and shown with citations (F20) | `ingest/sources.py`, Sprint 6 | partial |
| R8 | Cost per query and monthly projections from the query log | `reports/cost.md` | Haiku ~$0.0003 / query (projected) |

## Manage: controls and response

| Risk | Control in code or process | File |
| --- | --- | --- |
| R1 | Answers only from retrieved passages; refusal when the best similarity is below 0.65; refusal when the model says NOT_FOUND; refusal when no valid citation remains | `rag/answer.py` |
| R1 | Unretrieved citation IDs are stripped, so an invented ID can never be shown as a source | `rag/answer.py` (`extract_citations`, `resolve`) |
| R2 | Citations print the exact book, chapter and page, or surah:ayah, or collection and hadith number, from stored metadata, never from model text | `ingest/sources.py` (`citation`) |
| R3 | `.gitignore`; pre-commit hook; pre-push full-history scan; demo uses only self-written samples | `.gitignore`, `scripts/leak_check.py`, `samples/` |
| R4 | System prompt: present each view with its own citation; don't take sides or rank sources | `rag/answer.py` (`SYSTEM`, rule 8) |
| R5 | System prompt: no rulings, attribute, refer to a scholar. UI disclaimer | `rag/answer.py` (rule 5), `web/` |
| R6 | System prompt: flag weak or disputed grades. Grades shown with hadith citations | `rag/answer.py` (rule 7), `ingest/sources.py` |
| R7 | Every claim is numbered and linked to its passage. The citation drawer shows the source text. UI disclaimer | `web/` |
| R8 | Default model is local ($0); answer cache; prompt caching; cost logged per query | `rag/providers`, `rag/log.py` |

**Response plan.** If a hallucinated or misattributed source is found: add the question to the golden
set as a trap, reproduce it with `python -m evals.run`, fix the retrieval, prompt or threshold, and
re-run the eval before the next push. If a leak is found: stop pushing, rewrite history to remove it
(`git filter-repo`), force-push, and rotate anything that leaked.
