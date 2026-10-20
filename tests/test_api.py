import pytest
from fastapi.testclient import TestClient

import api.main as m
from rag.answer import retrieval_query
from rag.retrieve import retrieve
from tests.conftest import FakeProvider


@pytest.fixture
def client(store, tmp_path, monkeypatch):
    s = m.Settings()
    s.data_dir = tmp_path / "data"
    s.min_similarity = 0.15
    hit = retrieve(store, "patience hardship", k=1)[0]
    fake = FakeProvider(f"Patience means staying steady [{hit.id}].")
    monkeypatch.setattr(m, "settings", lambda: s)
    monkeypatch.setattr(m, "store", lambda: store)
    monkeypatch.setattr(m, "provider", lambda spec: fake)
    m.CONVERSATIONS.clear()
    c = TestClient(m.app)
    c.fake, c.hit = fake, hit
    return c


def test_ask_returns_answer_with_citations(client):
    r = client.post("/api/ask", json={"question": "What is patience in hardship?"})
    assert r.status_code == 200
    d = r.json()
    assert not d["refused"] and "[1]" in d["answer"]
    assert d["citations"][0]["id"] == client.hit.id
    assert d["citations"][0]["label"].startswith("The Garden of Patience")
    assert d["conversation_id"]


def test_off_topic_is_refused(client):
    d = client.post("/api/ask", json={"question": "What is the capital of Australia?"}).json()
    assert d["refused"] and d["answer"] == "Not found in your library."


def test_chunk_endpoint_serves_passage(client):
    d = client.get(f"/api/chunk/{client.hit.id}").json()
    assert "sample" in d["text"].lower() and d["meta"]["book_id"] == "garden-of-patience"
    assert client.get("/api/chunk/nope:1:0-0").status_code == 404


def test_empty_question_rejected(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422


def test_follow_up_uses_previous_turn(client):
    first = client.post("/api/ask", json={"question": "What is patience in hardship?"}).json()
    cid = first["conversation_id"]
    second = client.post("/api/ask", json={"question": "And what are its three kinds?", "conversation_id": cid}).json()
    assert second["conversation_id"] == cid
    assert m.CONVERSATIONS[cid][0][0] == "What is patience in hardship?"
    assert len(m.CONVERSATIONS[cid]) == 2
    assert client.fake.calls == 2           # different history -> not served from the answer cache


def test_retrieval_query_joins_previous_question():
    assert retrieval_query("what about the second one?", [("What are the kinds of patience?", "...")]) \
        == "What are the kinds of patience? what about the second one?"
    assert retrieval_query("q", None) == "q"
