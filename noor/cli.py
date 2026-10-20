"""Noor command line."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import typer

from noor.config import Settings

# Windows consoles default to cp1252; book text has transliteration marks (ḥ, ʿ) and smart quotes.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(help="Noor: answers from your Islamic library, with a citation for every claim.",
                  no_args_is_help=True)
sources_app = typer.Typer(help="Quran and hadith from the open fawazahmed0 APIs.", no_args_is_help=True)
app.add_typer(sources_app, name="sources")


def _store(s: Settings):
    from rag.embed import OllamaEmbedder
    from rag.store import Store
    return Store(s.data_dir, OllamaEmbedder(s.embed_model, s.ollama_host))


@app.command()
def ingest(
    library: Path = typer.Argument(None, help="Library folder <book>/<chapter>.json (default: NOOR_LIBRARY)"),
    books: str = typer.Option("", help="Comma list of book ids to index (default: all)"),
    sources: bool = typer.Option(True, help="Also index pulled Quran/hadith sources in data/sources/"),
):
    """Index every book in LIBRARY (plus pulled sources). Re-runs only changed chapters."""
    from ingest.reader import read_library
    from ingest.sources import read_sources

    s = Settings()
    lib = library or s.library
    if lib is None or not Path(lib).is_dir():
        typer.echo(f"Library folder not found: {lib}. Pass a path or set NOOR_LIBRARY in .env.")
        raise typer.Exit(1)
    only = {b.strip() for b in books.split(",") if b.strip()}
    chapters = [c for c in read_library(Path(lib), skip=s.skip_books) if not only or c.book_id in only]
    if sources:
        chapters += [c for c in read_sources(s.sources_dir) if not only or c.book_id in only]
    typer.echo(f"Indexing {len(chapters)} chapters from {len({c.book_id for c in chapters})} books ...")
    t0 = time.perf_counter()
    stats = _store(s).ingest(chapters, progress=typer.echo)
    typer.echo(f"Done in {time.perf_counter() - t0:.0f}s: {stats['reindexed']} chapters re-indexed, "
               f"{stats['chapters'] - stats['reindexed']} unchanged, {stats['chunks']} chunks written.")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Your question"),
    model: str = typer.Option(None, help="Override NOOR_MODEL, e.g. claude-haiku or ollama:qwen2.5:7b"),
    show_passages: bool = typer.Option(False, "--passages", help="Print the retrieved passages too"),
    cache: bool = typer.Option(True, help="Reuse a cached answer for a repeated question"),
):
    """Answer QUESTION from the library, with numbered citations."""
    from ingest.sources import citation
    from rag.answer import ask as run
    from rag.providers import get_provider

    s = Settings()
    provider = get_provider(model or s.model, s.ollama_host)
    a = run(question, _store(s), provider, s.db_path, k=s.top_k, min_similarity=s.min_similarity,
            use_cache=cache)
    typer.echo(a.text)
    if a.refused:
        typer.echo(f"\n({a.reason})")
    else:
        typer.echo("\nSources:")
        for n, h in a.citations:
            typer.echo(f"  [{n}] {citation(h.meta)}  <{h.id}>")
    if show_passages:
        for h in a.hits:
            typer.echo(f"\n--- {h.id}  sim={h.similarity:.3f} bm25={h.bm25:.1f}\n{h.text[:600]}")
    g = a.generation
    if a.cached:
        typer.echo("\n(answer cache hit: $0, no model call)")
    elif g:
        typer.echo(f"\n{g.model} | {g.tokens_in} in / {g.tokens_out} out | ${g.cost_usd:.5f} | {g.latency_ms} ms")


@app.command()
def log(limit: int = typer.Option(10, help="Rows to show")):
    """Show the most recent queries from the log (data/noor.db)."""
    s = Settings()
    if not s.db_path.exists():
        typer.echo("No queries logged yet.")
        return
    con = sqlite3.connect(s.db_path)
    rows = con.execute("select ts, model, tokens_in, tokens_out, cost_usd, latency_ms, refused, cited_ids "
                       "from queries order by id desc limit ?", (limit,)).fetchall()
    for ts, m, tin, tout, c, lat, ref, cited in rows:
        typer.echo(f"{ts}  {m:24} {tin:>6} in {tout:>5} out  ${c:.5f}  {lat:>6} ms  "
                   f"{'REFUSED' if ref else len(json.loads(cited)):>7} {'' if ref else 'cites'}")


@sources_app.command("pull")
def sources_pull(names: str = typer.Argument("quran,bukhari", help="Comma list: quran,bukhari,muslim,...")):
    """Download Quran/hadith editions into data/sources/ (git-ignored)."""
    from ingest.sources import pull
    s = Settings()
    for name in [n.strip() for n in names.split(",") if n.strip()]:
        for p in pull(name, s.sources_dir):
            typer.echo(f"  {name}: {p.relative_to(s.data_dir.parent)} ({p.stat().st_size // 1024} KB)")
    typer.echo("Now run: noor ingest")


if __name__ == "__main__":
    app()
