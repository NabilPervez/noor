"""Sprint 6 features (F11-F20), on the sample book with fake models."""
from datetime import date

import yaml

from ingest.sources import HADITH, hadith_chapters
from rag.chunk import chunk_chapter
from rag.features import (bad_answers, book_reader_link, chapter_hits, compare, confidence, daily,
                          export_notes, glossary, glossary_terms, grade_flag, quiz_count, record_feedback,
                          save_note, study)
from rag.retrieve import retrieve
from rag.terms import expand, find_terms, lookup
from tests.conftest import FakeProvider, fixture

MIN_SIM = 0.15


# F11
def test_book_reader_link_format():
    meta = {"kind": "book", "book_id": "the-straight-path", "chapter_id": "003-part-3", "block_start": 12}
    assert book_reader_link(meta, "http://localhost:5173/") == \
        "http://localhost:5173/?book=the-straight-path&chapter=003-part-3&block=12"
    assert book_reader_link(meta, None) is None                         # off unless configured
    assert book_reader_link({**meta, "kind": "quran"}, "http://x") is None  # only library books


# F12
def test_arabic_terms_expand_queries():
    assert find_terms("What do my books say about Ṣabr and tawakkul?") == ["sabr", "tawakkul"]
    assert "patience" in expand("What is sabr?")
    assert expand("What is patience?") == "What is patience?"
    assert lookup("Zakat")[0] == "zakah"


def test_term_expansion_finds_english_passage(store):
    hits = retrieve(store, expand("What is shukr?"), k=1)
    assert hits[0].meta["chapter_id"] == "002-gratitude"


# F13
def test_confidence_threshold():
    assert confidence(0.80) == "strong" and confidence(0.75) == "strong"
    assert confidence(0.749) == "partial" and confidence(0.66) == "partial"


# F14
def test_feedback_records_and_lists_bad_answers(tmp_path):
    db = tmp_path / "q.db"
    record_feedback(db, query_id=1, question="good one", vote=1, cited_ids=["a"])
    record_feedback(db, query_id=2, question="bad one", vote=-1, cited_ids=["b:1"], comment="wrong book")
    bad = bad_answers(db)
    assert [b["question"] for b in bad] == ["bad one"] and bad[0]["cited_ids"] == ["b:1"]


def test_promote_writes_ids_only(tmp_path, monkeypatch):
    import evals.promote as p
    db = tmp_path / "q.db"
    record_feedback(db, query_id=2, question="bad one", vote=-1, cited_ids=["b:1"])
    monkeypatch.setattr(p, "CANDIDATES", tmp_path / "candidates.yaml")
    monkeypatch.setattr(p, "Settings", lambda: type("S", (), {"db_path": db})())
    assert p.promote() == 1 and p.promote() == 0                       # no duplicates on re-run
    c = yaml.safe_load((tmp_path / "candidates.yaml").read_text())["candidates"][0]
    assert c["q"] == "bad one" and c["expect"] == [] and c["bad_answer_cited"] == ["b:1"]


# F15
def test_notebook_export_markdown(tmp_path):
    db = tmp_path / "q.db"
    save_note(db, "What is patience?", "Staying steady [1].",
              [{"n": 1, "id": "garden-of-patience:001-patience:0-3", "label": "The Garden of Patience (sample), On Patience"}])
    md = export_notes(db)
    assert md.startswith("# Noor notebook") and "## What is patience?" in md
    assert "1. The Garden of Patience (sample), On Patience (`garden-of-patience:001-patience:0-3`)" in md


# F16
def test_compare_answers_per_book_and_refuses_weak_book(store):
    hit = retrieve(store, "patience hardship", k=1, where={"book_id": "garden-of-patience"})[0]
    views = compare("patience in hardship", ["garden-of-patience", "no-such-book"], store,
                    FakeProvider(f"It says to stay steady [{hit.id}]."), min_similarity=MIN_SIM)
    assert not views[0].answer.refused and views[0].answer.citations[0][1].id == hit.id
    assert views[1].answer.refused                                       # nothing from that book


def test_retrieve_where_filter_stays_inside_book(store):
    hits = retrieve(store, "gratitude", k=5, where={"chapter_key": "garden-of-patience/001-patience"})
    assert hits and all(h.meta["chapter_key"] == "garden-of-patience/001-patience" for h in hits)


# F17
def test_study_mode_cites_chapter_and_counts_quiz(store):
    hits = chapter_hits(store, "garden-of-patience/001-patience")
    cid = hits[0].id
    reply = (f"SUMMARY: Patience is staying steady [{cid}].\nQUIZ:\n"
             + "\n".join(f"{i}. Q{i}? Answer: A{i} [{cid}]" for i in range(1, 6)))
    a = study("garden-of-patience/001-patience", store, FakeProvider(reply))
    assert not a.refused and a.citations[0][1].id == cid and quiz_count(a.text) == 5
    assert study("garden-of-patience/999-missing", store, FakeProvider()).refused


# F18
def test_daily_is_deterministic_per_date(store):
    a = daily(store, date(2026, 10, 20), kinds=("book",))
    b = daily(store, date(2026, 10, 20), kinds=("book",))
    assert a[0].id == b[0].id and a[1] == b[1] and a[1].endswith("?")


# F19
def test_glossary_has_25_terms_and_cites_library(store):
    assert len(glossary_terms()) >= 25
    entry, hits = glossary("sabr", store)
    assert entry[0] == "sabr" and "Patience" in entry[2]
    assert hits and hits[0].meta["chapter_id"] == "001-patience"
    assert glossary("not-a-term", store) == (None, [])


# F20
def test_weak_grade_flag_from_hadith_fixture():
    HADITH.setdefault("sample", ("eng-sample", "Sample Collection", "Test Compiler"))
    chunks = [c for ch in hadith_chapters("sample", fixture("hadith-sample.json")) for c in chunk_chapter(ch)]
    flags = {c.id: grade_flag(c.grades) for c in chunks}
    assert flags == {"sample:1": None, "sample:2": None, "sample:3": "weak"}
    assert grade_flag("Al-Albani: Hasan Sahih") is None and grade_flag("Zubair: Da'if") == "weak"
