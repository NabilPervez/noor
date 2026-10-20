# Data inventory

*Last updated 2026-10-20.* Classes: **public** (may be published), **personal** (owner's own data, local
only), **copyrighted-private** (third-party copyrighted text, local only, never committed).

Copyright status is the owner's best understanding, not legal advice. Where it is uncertain the
inventory says so, and the item is treated as copyrighted-private, the safe default.

## Corpus

| Source | Author / translator | Copyright status | Class | Stored at | In Noor index |
| --- | --- | --- | --- | --- | --- |
| Addressing the Impact of Trauma on Faith | Najwa Awad & Sarah Sultan | Copyrighted (modern publication) | copyrighted-private | `D:\Code\book-reader\public\library\` | yes |
| Beginning of Guidance (Bidayat al-Hidaya) | Al-Ghazali, tr. Muhammad Abul Quasem | Original public domain; translation assumed copyrighted | copyrighted-private | same | yes |
| The Ninety-Nine Beautiful Names of God | Al-Ghazali, tr. Robert Charles Stade | Original public domain; translation assumed copyrighted | copyrighted-private | same | yes |
| Proofs for the Prophethood of Muhammad | Mohammad Elshinawy | Copyrighted (modern publication) | copyrighted-private | same | yes |
| Qur'an 30 for 30: Thematic Tafsir | Omar Suleiman & Ismail Kamdar | Copyrighted (modern publication) | copyrighted-private | same | yes |
| The Alchemy of Happiness | Al-Ghazali | Original public domain; translation edition not recorded, so unknown | copyrighted-private | same | yes |
| The Refinement of Character | Imam Ibn Qudamah al-Maqdisi | Original public domain; translation assumed copyrighted | copyrighted-private | same | yes |
| The Sirah of the Prophet | Dr. Yasir Qadhi | Copyrighted (modern publication) | copyrighted-private | same | yes |
| The Straight Path | Author not recorded in metadata | Unknown | copyrighted-private | same | yes |
| Trials and Tribulations | Author not recorded in metadata | Unknown | copyrighted-private | same | yes |
| The Clear Quran (library PDF copy) | Dr. Mustafa Khattab | Copyrighted translation | copyrighted-private | same | **no** (duplicate of the API copy; `NOOR_SKIP_BOOKS`) |
| Sahih al-Bukhari (library PDF copy) | al-Bukhari, English translation | Translation assumed copyrighted | copyrighted-private | same | **no** (duplicate of the API copy) |
| Quran, `eng-mustafakhattaba` edition | Dr. Mustafa Khattab, via fawazahmed0/quran-api | Copyrighted translation, redistributed by the API | copyrighted-private | `data/sources/` (git-ignored) | yes |
| Sahih al-Bukhari, `eng-bukhari` edition | via fawazahmed0/hadith-api | Translation assumed copyrighted; grades as given by the API | copyrighted-private | `data/sources/` (git-ignored) | yes |
| Sample book "The Garden of Patience" | Written for this repo | Original, owned by the repo | public | `samples/library/` | tests only |
| Test fixtures (Quran/hadith shapes) | Written for this repo | Original | public | `tests/fixtures/` | tests only |

## Derived data (all local, all git-ignored)

| Data | Contains | Class | Stored at |
| --- | --- | --- | --- |
| Chunks and embeddings | Passage text and vectors derived from it | copyrighted-private | `data/chroma/` |
| BM25 index | Tokenized passage text | copyrighted-private | `data/bm25-*.pkl` |
| Ingest manifest | Chapter keys and content hashes, no text | personal | `data/manifest-*.json` |
| Query log | Questions, model, tokens, cost, latency, chunk IDs; **no passage text** | personal | `data/noor.db` (`queries`) |
| Answer cache | Generated answers, which may quote passages | copyrighted-private | `data/noor.db` (`answer_cache`) |
| Eval results | Questions, answers, judge verdicts | copyrighted-private | `data/evals/` |
| Feedback and notebook (Sprint 6) | Saved answers, thumbs up/down | personal / copyrighted-private | `data/` |

## Published data (in the public repository)

Code, docs, the self-written sample book and fixtures, `evals/golden.yaml` (self-written questions and
source IDs only), `reports/*.md` (numbers, IDs and self-written question text only).

## Controls

- `.gitignore` excludes `data/`, `library/`, `.env`, `*.db` and `chroma/`.
- `scripts/leak_check.py` runs as a pre-commit hook and before every push. It blocks protected paths and
  book-shaped JSON, and it fails if any 12-word run from the real library or the downloaded API text
  appears in a staged file or anywhere in git history.
- The owner's separate `book-reader` repository is public and currently commits its converted library.
  That is outside Noor's controls, and it is flagged to the owner.
