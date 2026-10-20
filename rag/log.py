"""Per-query log and answer cache in SQLite (data/noor.db, git-ignored).
The query log stores numbers and chunk IDs, never passage text."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
create table if not exists queries (
  id integer primary key,
  ts text not null,
  question text not null,
  model text not null,
  tokens_in integer not null,
  tokens_out integer not null,
  cost_usd real not null,
  latency_ms integer not null,
  retrieval_ms integer not null,
  chunk_ids text not null,      -- JSON list: everything retrieved
  cited_ids text not null,      -- JSON list: what the answer actually cited
  top_similarity real not null,
  refused integer not null
);
create table if not exists answer_cache (
  key text primary key,
  model text not null,
  answer text not null,         -- JSON: text, refused, cited ids, reason (local only)
  created text not null
);
"""
# Columns added after Sprint 1; added in place to existing databases.
MIGRATIONS = {"cached": "integer not null default 0", "cache_read": "integer not null default 0",
              "cache_write": "integer not null default 0", "tag": "text not null default ''"}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    have = {r[1] for r in con.execute("pragma table_info(queries)")}
    for col, decl in MIGRATIONS.items():
        if col not in have:
            con.execute(f"alter table queries add column {col} {decl}")
    return con


def log_query(path: Path, *, question: str, model: str, tokens_in: int, tokens_out: int,
              cost_usd: float, latency_ms: int, retrieval_ms: int, chunk_ids: list[str],
              cited_ids: list[str], top_similarity: float, refused: bool, cached: bool = False,
              cache_read: int = 0, cache_write: int = 0, tag: str = "") -> int:
    with connect(path) as con:
        cur = con.execute(
            "insert into queries (ts, question, model, tokens_in, tokens_out, cost_usd, latency_ms,"
            " retrieval_ms, chunk_ids, cited_ids, top_similarity, refused, cached, cache_read,"
            " cache_write, tag) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), question, model, tokens_in,
             tokens_out, cost_usd, latency_ms, retrieval_ms, json.dumps(chunk_ids),
             json.dumps(cited_ids), round(top_similarity, 4), int(refused), int(cached),
             cache_read, cache_write, tag))
        return cur.lastrowid


def cache_get(path: Path, key: str) -> dict | None:
    with connect(path) as con:
        row = con.execute("select answer from answer_cache where key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def cache_put(path: Path, key: str, model: str, answer: dict) -> None:
    with connect(path) as con:
        con.execute("insert or replace into answer_cache values (?,?,?,?)",
                    (key, model, json.dumps(answer), datetime.now(timezone.utc).isoformat(timespec="seconds")))
