import json
from pathlib import Path

import pytest

from ingest.reader import read_library
from rag.embed import FakeEmbedder
from rag.providers import Generation
from rag.store import Store

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "library"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path) -> Store:
    s = Store(tmp_path / "data", FakeEmbedder())
    s.ingest(read_library(SAMPLES))
    return s


class FakeProvider:
    """Returns a canned answer; records whether it was called."""
    name = "fake-llm"

    def __init__(self, reply: str = "NOT_FOUND"):
        self.reply, self.calls = reply, 0

    def generate(self, system: str, user: str) -> Generation:
        self.calls += 1
        return Generation(self.reply, self.name, 1000, 100, 5, 0.0)
