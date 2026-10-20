import sqlite3

from rag.answer import NOT_FOUND, ask, extract_citations
from rag.retrieve import retrieve
from tests.conftest import FakeProvider

MIN_SIM = 0.15   # FakeEmbedder scale; the real threshold is set in .env / Settings


def test_off_topic_question_is_refused_without_calling_the_model(store, tmp_path):
    llm = FakeProvider("should never be used")
    a = ask("What is the capital of Australia?", store, llm, tmp_path / "q.db", min_similarity=MIN_SIM)
    assert a.refused and a.text == NOT_FOUND
    assert llm.calls == 0


def test_answer_cites_retrieved_chunks_with_numbers(store, tmp_path):
    hit = retrieve(store, "patience hardship", k=1)[0]
    llm = FakeProvider(f"Patience means staying steady [{hit.id}]. Also [made-up:book:1-2].")
    a = ask("What is patience in hardship?", store, llm, tmp_path / "q.db", min_similarity=MIN_SIM)
    assert not a.refused
    assert "[1]" in a.text and "made-up" not in a.text
    assert [h.id for _, h in a.citations] == [hit.id]


def test_model_not_found_becomes_refusal(store, tmp_path):
    a = ask("What is patience in hardship?", store, FakeProvider("NOT_FOUND"), tmp_path / "q.db",
            min_similarity=MIN_SIM)
    assert a.refused and a.text == NOT_FOUND


def test_answer_without_valid_citations_is_refused(store, tmp_path):
    a = ask("What is patience in hardship?", store, FakeProvider("Patience is good, trust me."),
            tmp_path / "q.db", min_similarity=MIN_SIM)
    assert a.refused


def test_every_ask_logs_one_row_without_passage_text(store, tmp_path):
    db = tmp_path / "q.db"
    ask("What is the capital of Australia?", store, FakeProvider(), db, min_similarity=MIN_SIM)
    hit = retrieve(store, "gratitude", k=1)[0]
    ask("What is gratitude?", store, FakeProvider(f"Noticing blessings [{hit.id}]."), db, min_similarity=MIN_SIM)
    con = sqlite3.connect(db)
    cols = [r[1] for r in con.execute("pragma table_info(queries)")]
    for needed in ("model", "tokens_in", "tokens_out", "cost_usd", "latency_ms", "chunk_ids"):
        assert needed in cols
    rows = con.execute("select refused, tokens_in, cited_ids from queries order by id").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == 1 and rows[1][0] == 0 and rows[1][1] == 1000
    passage = store.col.get(ids=[hit.id])["documents"][0]
    dump = "\n".join(str(r) for r in con.execute("select * from queries"))
    assert passage[:60] not in dump


def test_single_ayah_citation_maps_to_its_retrieved_passage():
    allowed = ["quran:11:8-14", "quran:2:153"]
    text, cited = extract_citations("Patience [quran:11:11]. And [quran:2:153]. Not [quran:11:20].", allowed)
    assert cited == ["quran:11:8-14", "quran:2:153"]
    assert text == "Patience [1]. And [2]. Not ."


def test_extract_citations_handles_lists_and_repeats():
    text, cited = extract_citations("A [x:1:0-2; y:2:3-4]. B [x:1:0-2].", ["x:1:0-2", "y:2:3-4"])
    assert text == "A [1, 2]. B [1]."
    assert cited == ["x:1:0-2", "y:2:3-4"]


def test_cost_math():
    from rag.providers import cost
    assert cost("claude-haiku-5-5", 1_000_000, 1_000_000) == 0.60
    assert cost("claude-sonnet-5-5", 4000, 400) == 0.012
    assert cost("ollama:qwen2.5:7b", 4000, 400) == 0.0
    # cache write 1M at $0.125, cache read 1M at $0.01 (Haiku 5.5)
    assert cost("claude-haiku-5-5", 0, 0, cache_write=1_000_000) == 0.125
    assert cost("claude-haiku-5-5", 0, 0, cache_read=1_000_000) == 0.01


def test_system_prompt_is_long_enough_to_cache():
    from rag.answer import SYSTEM
    from rag.chunk import tokens
    assert tokens(SYSTEM) > 512 * 1.1      # 512-token minimum for Haiku/Sonnet 5.5, with margin


def test_repeat_question_hits_answer_cache(store, tmp_path):
    db = tmp_path / "q.db"
    hit = retrieve(store, "gratitude", k=1)[0]
    llm = FakeProvider(f"Noticing blessings [{hit.id}].")
    a1 = ask("What is gratitude?", store, llm, db, min_similarity=MIN_SIM)
    a2 = ask("  what is GRATITUDE ", store, llm, db, min_similarity=MIN_SIM)   # normalizes the same
    assert llm.calls == 1
    assert a2.cached and not a1.cached
    assert a2.text == a1.text and [h.id for _, h in a2.citations] == [hit.id]
    rows = sqlite3.connect(db).execute("select cached, cost_usd, tokens_in from queries order by id").fetchall()
    assert rows[1] == (1, 0.0, 0)


def test_cache_key_changes_with_model_and_index(store):
    from rag.answer import cache_key
    k1 = cache_key("q", "m1", store, 6, 0.65)
    assert k1 == cache_key("Q?", "m1", store, 6, 0.65)
    assert k1 != cache_key("q", "m2", store, 6, 0.65)
    store.manifest["new/chapter"] = "abc"
    assert k1 != cache_key("q", "m1", store, 6, 0.65)


def test_no_cache_flag_always_calls_model(store, tmp_path):
    hit = retrieve(store, "gratitude", k=1)[0]
    llm = FakeProvider(f"Noticing blessings [{hit.id}].")
    for _ in range(2):
        ask("What is gratitude?", store, llm, tmp_path / "q.db", min_similarity=MIN_SIM, use_cache=False)
    assert llm.calls == 2
