from evals.report import verdict
from evals.run import load_golden, matches, summarize
from rag.store import fold, stem, tokenize


def test_golden_set_shape():
    qs = load_golden()
    assert 30 <= len(qs) <= 50
    una = [q for q in qs if not q["answerable"]]
    assert 5 <= len(una) <= 10
    assert all(q["expect"] for q in qs if q["answerable"])
    assert len({q["id"] for q in qs}) == len(qs)


def test_matcher_quran_range_chapter_prefix_and_hadith():
    assert matches("quran:2:150-156", {}, "quran:2:153")
    assert not matches("quran:2:150-152", {}, "quran:2:153")
    assert not matches("quran:3:150-156", {}, "quran:2:153")
    assert matches("x:1:0-4", {"chapter_key": "the-alchemy-of-happiness/002-chapter-i"}, "the-alchemy-of-happiness/")
    assert matches("bukhari:13", {}, "bukhari:13") and matches("bukhari:13.1", {}, "bukhari:13")
    assert not matches("bukhari:130", {}, "bukhari:13")


def test_verdict_needs_every_threshold():
    ok = {"hit_rate": .9, "grounded_rate": .95, "refusal_rate_unanswerable": 1.0, "answered_rate": .85}
    assert verdict(ok) == ("GO", [])
    v, fails = verdict({**ok, "refusal_rate_unanswerable": 8 / 9})
    assert v == "NO-GO" and fails == ["Refusal on unanswerable"]


def test_summarize_counts():
    rows = [{"answerable": True, "hit": True, "refused": False, "grounded": True, "cited_expected": True,
             "latency_ms": 100, "cost_usd": 0.0, "tokens_in": 10},
            {"answerable": False, "hit": None, "refused": True, "latency_ms": 5, "cost_usd": 0.0, "tokens_in": 0}]
    s = summarize(rows)
    assert s["hit_rate"] == 1.0 and s["refusal_rate_unanswerable"] == 1.0 and s["grounded_rate"] == 1.0


def test_keyword_normalization():
    assert fold("al-Wadūd") == "al-wadud"
    assert tokenize("Al-Wadūd") == tokenize("al wadud")
    assert stem("loving") == stem("love") == stem("loves")
    assert stem("intentions") == stem("intention")
    assert stem("kindness") == "kindness"
