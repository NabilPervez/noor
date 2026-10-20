"""Leak gate: proves no book text is (or ever was) in this repo.

  python scripts/leak_check.py            full pre-push audit (exit 0 = safe to push)
  python scripts/leak_check.py --staged   pre-commit check of staged files only

A "leak" is any run of 12 consecutive words that also appears in the real library
(NOOR_LIBRARY) or in downloaded Quran/hadith files (data/sources/). The check fails
closed: if the library can't be read, nothing can be proven clean, so it exits 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = 12
WORD = re.compile(r"[^\W_]+", re.UNICODE)
MUST_IGNORE = ["data/", "data/chroma/", "data/noor.db", "data/sources/x.json", ".env", "library/x/001.json"]
BLOCKED_PATH = re.compile(r"^(?!samples/)(.*/)?(library|data|chroma)/|(^|/)\.env$|\.(db|sqlite3?)$")
SAMPLES_MAX_BYTES = 3 * 1024


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


def shingles(text: str) -> set[int]:
    w = words(text)
    return {hash(" ".join(w[i:i + N])) for i in range(len(w) - N + 1)}


def _env_library() -> Path | None:
    lib = os.environ.get("NOOR_LIBRARY")
    env = ROOT / ".env"
    if not lib and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("NOOR_LIBRARY="):
                lib = line.split("=", 1)[1].strip()
    return Path(lib) if lib else None


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def reference_shingles() -> set[int]:
    """Shingles of every passage in the real library and any downloaded API data."""
    lib = _env_library()
    if not lib or not lib.is_dir():
        sys.exit(f"FAIL: library not found (NOOR_LIBRARY={lib}). Cannot prove the repo is clean.")
    ref: set[int] = set()
    files = [p for p in lib.glob("*/*.json") if p.name != "book.json"]
    for p in files:
        for b in json.loads(p.read_text(encoding="utf-8")).get("blocks", []):
            ref |= shingles(b.get("text", ""))
    src = ROOT / "data" / "sources"
    for p in src.glob("*.json") if src.is_dir() else []:
        for s in _walk_strings(json.loads(p.read_text(encoding="utf-8"))):
            ref |= shingles(s)
    if len(files) == 0 or len(ref) < 1000:
        sys.exit(f"FAIL: library at {lib} looks empty ({len(files)} files). Refusing to vouch.")
    print(f"  reference: {len(files)} chapter files, {len(ref):,} 12-word runs")
    return ref


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def looks_like_book_json(text: str) -> bool:
    try:
        d = json.loads(text)
    except ValueError:
        return False
    blocks = d.get("blocks") if isinstance(d, dict) else None
    return isinstance(blocks, list) and any(isinstance(b, dict) and "text" in b for b in blocks)


def check_paths_and_content(items: list[tuple[str, str]], ref: set[int] | None) -> list[str]:
    """items = (path, content). Returns problems; empty means clean."""
    problems = []
    for path, content in items:
        if BLOCKED_PATH.search(path):
            problems.append(f"{path}: path must never be committed")
        if path.endswith(".json") and not path.startswith("samples/") and looks_like_book_json(content):
            problems.append(f"{path}: book-shaped JSON (blocks with text) outside samples/")
        if ref is not None:
            hits = shingles(content) & ref
            if hits:
                problems.append(f"{path}: {len(hits)} 12-word runs match the real library")
    return problems


def staged() -> int:
    names = [n for n in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if n]
    items = [(n, git("show", f":{n}")) for n in names]
    ref = reference_shingles() if items else None
    problems = check_paths_and_content(items, ref)
    for p in problems:
        print("BLOCKED:", p)
    return 1 if problems else 0


def full() -> int:
    fails = []
    print("1. git-ignore rules")
    for path in MUST_IGNORE:
        if not git("check-ignore", "--no-index", path).strip():
            fails.append(f"not ignored: {path}")

    print("2. pre-commit hook")
    hook = ROOT / ".git" / "hooks" / "pre-commit"
    if not hook.exists() or "leak_check.py --staged" not in hook.read_text(encoding="utf-8"):
        fails.append("pre-commit hook missing: run python scripts/install_hooks.py")
    ref = reference_shingles()
    lib = _env_library()
    real = next(p for p in sorted(lib.glob("*/*.json")) if p.name != "book.json")
    real_text = " ".join(b["text"] for b in json.loads(real.read_text(encoding="utf-8"))["blocks"])
    probes = [("library/x/001.json", "{}"), ("notes.md", real_text),
              ("x.json", json.dumps({"blocks": [{"t": "p", "text": "x"}]}))]
    for path, content in probes:
        if not check_paths_and_content([(path, content)], ref):
            fails.append(f"hook logic would NOT block probe {path}")

    print("3. full history scan (git log -p --all)")
    added = "\n".join(l[1:] for l in git("log", "-p", "--all", "--no-color").splitlines()
                      if l.startswith("+") and not l.startswith("+++"))
    hits = shingles(added) & ref
    if hits:
        fails.append(f"history contains {len(hits)} 12-word runs from the library")

    print("4. samples/ are self-written and small")
    tracked = [n for n in git("ls-files").splitlines() if n]
    for n in tracked:
        if n.startswith("samples/") and (ROOT / n).stat().st_size > SAMPLES_MAX_BYTES:
            fails.append(f"{n} is over {SAMPLES_MAX_BYTES} bytes")
    items = [(n, (ROOT / n).read_text(encoding="utf-8", errors="replace")) for n in tracked]
    fails += check_paths_and_content(items, ref)

    for f in fails:
        print("FAIL:", f)
    print("LEAK CHECK:", "FAILED - do not push" if fails else "PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    sys.exit(staged() if ap.parse_args().staged else full())
