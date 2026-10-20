"""Noor command line. Commands are stubs until Sprint 1."""
from pathlib import Path

import typer

app = typer.Typer(help="Noor: answers from your Islamic library, with a citation for every claim.",
                  no_args_is_help=True)
sources_app = typer.Typer(help="Quran and hadith from the open fawazahmed0 APIs.")
app.add_typer(sources_app, name="sources")


def _todo(sprint: int) -> None:
    typer.echo(f"Not built yet (Sprint {sprint}).")
    raise typer.Exit(code=2)


@app.command()
def ingest(library: Path = typer.Argument(..., help="Library folder: <book>/<chapter>.json")):
    """Index every book in LIBRARY. Re-runs only changed chapters."""
    _todo(1)


@app.command()
def ask(question: str = typer.Argument(..., help="Your question")):
    """Answer QUESTION from the library, with numbered citations."""
    _todo(1)


@sources_app.command("pull")
def sources_pull(names: str = typer.Argument("quran,bukhari", help="Comma list: quran,bukhari,muslim")):
    """Download Quran/hadith editions into data/sources/ (git-ignored)."""
    _todo(1)


if __name__ == "__main__":
    app()
