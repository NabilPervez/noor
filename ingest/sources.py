"""Quran and hadith from the open fawazahmed0 APIs (same sources as quran-reflection,
hadith-reflection and islamic-rag-quran-and-hadith). Raw downloads are cached in
data/sources/ (git-ignored) and converted to Chapters in the library's block shape.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import httpx

from ingest.reader import Block, Chapter

QURAN_BASES = ["https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1",
               "https://raw.githubusercontent.com/fawazahmed0/quran-api/1"]
HADITH_BASES = ["https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1",
                "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1"]
QURAN_EDITION = "eng-mustafakhattaba"     # The Clear Quran, Dr. Mustafa Khattab
HADITH = {
    "bukhari": ("eng-bukhari", "Sahih al-Bukhari", "Imam al-Bukhari"),
    "muslim": ("eng-muslim", "Sahih Muslim", "Imam Muslim"),
    "abudawud": ("eng-abudawud", "Sunan Abi Dawud", "Imam Abu Dawud"),
    "tirmidhi": ("eng-tirmidhi", "Jami at-Tirmidhi", "Imam at-Tirmidhi"),
    "nasai": ("eng-nasai", "Sunan an-Nasa'i", "Imam an-Nasa'i"),
    "ibnmajah": ("eng-ibnmajah", "Sunan Ibn Majah", "Imam Ibn Majah"),
}
SOURCES = ["quran", *HADITH]


def _fetch(bases: list[str], path: str) -> dict:
    last: Exception | None = None
    for base in bases:
        try:
            r = httpx.get(f"{base}/{path}", timeout=120, follow_redirects=True)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            last = e
    raise RuntimeError(f"could not download {path}: {last}")


def pull(name: str, dest: Path) -> list[Path]:
    """Download one source into dest (data/sources). Returns the files written."""
    dest.mkdir(parents=True, exist_ok=True)
    if name == "quran":
        files = {"quran-info.json": (QURAN_BASES, "info.json"),
                 f"quran-{QURAN_EDITION}.json": (QURAN_BASES, f"editions/{QURAN_EDITION}.min.json")}
    elif name in HADITH:
        ed = HADITH[name][0]
        files = {f"hadith-{ed}.json": (HADITH_BASES, f"editions/{ed}.min.json")}
    else:
        raise ValueError(f"unknown source {name!r}; choose from {', '.join(SOURCES)}")
    out = []
    for fname, (bases, path) in files.items():
        (dest / fname).write_text(json.dumps(_fetch(bases, path), ensure_ascii=False), encoding="utf-8")
        out.append(dest / fname)
    return out


def quran_chapters(info: dict, edition: dict) -> Iterator[Chapter]:
    names = {c["chapter"]: c for c in info.get("chapters", [])}
    by_surah: dict[int, list[Block]] = {}
    for v in edition["quran"]:
        s, a = int(v["chapter"]), int(v["verse"])
        blocks = by_surah.setdefault(s, [])
        blocks.append(Block(t="ayah", text=v["text"].strip(), index=len(blocks), ref=f"{s}:{a}"))
    for s, blocks in sorted(by_surah.items()):
        c = names.get(s, {})
        title = f"Surah {s}" + (f" {c['englishname']}" if c.get("englishname") else "") + \
                (f" ({c['name']})" if c.get("name") else "")
        yield Chapter(book_id="quran", book_title="The Quran (The Clear Quran, tr. Mustafa Khattab)",
                      author="", chapter_id=f"{s:03d}", chapter_title=title, blocks=blocks, kind="quran")


def hadith_chapters(name: str, data: dict) -> Iterator[Chapter]:
    _, title, author = HADITH[name]
    meta = data.get("metadata", {})
    sections = meta.get("sections") or meta.get("section") or {}
    details = meta.get("section_details") or meta.get("section_detail") or {}
    hadiths = [h for h in data.get("hadiths", []) if (h.get("text") or "").strip()]
    for key, sec_title in sections.items():
        d = details.get(key) or {}
        lo, hi = d.get("hadithnumber_first", 0), d.get("hadithnumber_last", -1)
        blocks = [Block(t="hadith", text=h["text"].strip(), index=i, ref=_num(h["hadithnumber"]),
                        grades=[g for g in h.get("grades", []) if g.get("grade")])
                  for i, h in enumerate(x for x in hadiths if lo <= x["hadithnumber"] <= hi)]
        if blocks and (sec_title or "").strip():
            yield Chapter(book_id=name, book_title=title, author=author, chapter_id=f"{int(key):03d}",
                          chapter_title=sec_title.strip(), blocks=blocks, kind="hadith")


def _num(n) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def read_sources(src_dir: Path) -> Iterator[Chapter]:
    """Chapters for every source already pulled into src_dir."""
    info_p = src_dir / "quran-info.json"
    ed_p = src_dir / f"quran-{QURAN_EDITION}.json"
    if ed_p.exists():
        info = json.loads(info_p.read_text(encoding="utf-8")) if info_p.exists() else {}
        yield from quran_chapters(info, json.loads(ed_p.read_text(encoding="utf-8")))
    for name, (ed, _, _) in HADITH.items():
        p = src_dir / f"hadith-{ed}.json"
        if p.exists():
            yield from hadith_chapters(name, json.loads(p.read_text(encoding="utf-8")))


def citation(meta: dict) -> str:
    """Human citation for a chunk's metadata."""
    kind = meta.get("kind")
    if kind == "quran":
        return f"Quran {meta['refs']}"
    if kind == "hadith":
        g = f" [{meta['grades']}]" if meta.get("grades") else ""
        return f"{meta['book_title']} {meta['refs']} ({meta['chapter_title']}){g}"
    p0, p1 = meta.get("page_start"), meta.get("page_end")
    page = "" if p0 in ("", None) else (f", p.{p0}" if p0 == p1 else f", pp.{p0}-{p1}")
    return f"{meta["book_title"]}, {meta["chapter_title"]}{page}"
