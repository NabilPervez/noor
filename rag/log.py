"""Per-query log in SQLite (data/noor.db, git-ignored). Stores numbers and chunk IDs, never passage text."""
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
)"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    return con


def log_query(path: Path, *, question: str, model: str, tokens_in: int, tokens_out: int,
              cost_usd: float, latency_ms: int, retrieval_ms: int, chunk_ids: list[str],
              cited_ids: list[str], top_similarity: float, refused: bool) -> int:
    with connect(path) as con:
        cur = con.execute(
            "insert into queries (ts, question, model, tokens_in, tokens_out, cost_usd, latency_ms,"
            " retrieval_ms, chunk_ids, cited_ids, top_similarity, refused)"
            " values (?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), question, model, tokens_in,
             tokens_out, cost_usd, latency_ms, retrieval_ms, json.dumps(chunk_ids),
             json.dumps(cited_ids), round(top_similarity, 4), int(refused)))
        return cur.lastrowid
