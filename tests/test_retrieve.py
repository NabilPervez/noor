import json

from ingest.reader import read_library
from rag.retrieve import retrieve, rrf
from tests.conftest import SAMPLES


def test_rrf_rewards_agreement():
    scores = rrf([["a", "b", "c"], ["b", "c", "a"]])
    assert max(scores, key=scores.get) == "b"
    assert set(scores) == {"a", "b", "c"}


def test_rrf_includes_ids_found_by_only_one_ranker():
    scores = rrf([["a"], ["z"]])
    assert set(scores) == {"a", "z"}


def test_retrieves_the_relevant_chapter(store):
    hits = retrieve(store, "What is patience when hardship arrives?", k=3)
    assert hits[0].meta["chapter_id"] == "001-patience"
    assert hits[0].similarity > 0 and hits[0].bm25 > 0


def test_keyword_pass_finds_rare_term(store):
    hits = retrieve(store, "shukr", k=3)
    assert hits and hits[0].meta["chapter_id"] == "002-gratitude"


def test_reingest_skips_unchanged_chapters(store):
    stats = store.ingest(read_library(SAMPLES))
    assert stats["reindexed"] == 0 and stats["chapters"] == 2


def test_changed_chapter_is_reindexed(store, tmp_path):
    lib = tmp_path / "lib"
    book = lib / "garden-of-patience"
    book.mkdir(parents=True)
    for f in (SAMPLES / "garden-of-patience").glob("*.json"):
        (book / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    ch = json.loads((book / "002-gratitude.json").read_text(encoding="utf-8"))
    ch["blocks"].append({"t": "p", "text": "An added test paragraph.", "page": 5})
    (book / "002-gratitude.json").write_text(json.dumps(ch), encoding="utf-8")
    stats = store.ingest(read_library(lib))
    assert stats["reindexed"] == 1
    assert store.count() == 2
