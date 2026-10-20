import json
from pathlib import Path

from typer.testing import CliRunner

from noor.cli import app

ROOT = Path(__file__).resolve().parent.parent


def test_help_lists_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("ingest", "ask", "sources"):
        assert cmd in result.output


def test_sample_library_matches_book_format():
    book = ROOT / "samples" / "library" / "garden-of-patience"
    assert json.loads((book / "book.json").read_text())["author"]
    for ch in book.glob("0*.json"):
        data = json.loads(ch.read_text())
        assert {"id", "title", "blocks"} <= data.keys()
        assert all({"t", "text"} <= b.keys() for b in data["blocks"])
