"""Write reports/cost.md from the bench rows in the query log (scripts/bench.py).

Measured: every model that has bench rows in data/noor.db.
Projected: Claude models without bench rows (no API key yet), priced from the token counts
measured on the local run. Numbers only; no passage text reaches the report.

  python scripts/cost_report.py
"""
import platform
import sqlite3
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from noor.config import Settings                          # noqa: E402
from rag.answer import SYSTEM                             # noqa: E402
from rag.chunk import tokens                              # noqa: E402
from rag.providers import PRICES, PRICES_DATE             # noqa: E402

VOLUMES = (100, 1_000, 10_000)
REPEAT_RATES = (0.10, 0.25, 0.50)


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))] if v else 0


def hardware() -> str:
    try:
        ps = ("(Get-CimInstance Win32_VideoController | ? Name -notmatch 'Virtual' | % Name) -join ', ';"
              "(Get-CimInstance Win32_Processor).Name;"
              "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)")
        gpu, cpu, ram = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                                       text=True, timeout=30).stdout.strip().splitlines()[:3]
        return f"{gpu} GPU, {cpu}, {ram} GB RAM"
    except Exception:
        return platform.processor() or "unknown"


def model_rows(con, model, tag):
    return con.execute("select tokens_in, tokens_out, cost_usd, latency_ms, refused, cached, cache_read,"
                       " cache_write from queries where model=? and tag=?", (model, tag)).fetchall()


def money(x: float) -> str:
    return "$0" if x == 0 else f"${x:,.2f}" if x >= 1 else f"${x:.4f}" if x >= 0.01 else f"${x:.6f}"


def main() -> None:
    s = Settings()
    con = sqlite3.connect(s.db_path)
    models = [m for (m,) in con.execute("select distinct model from queries where tag='bench-cold'")]
    if not models:
        sys.exit("No bench rows. Run: python scripts/bench.py --model <model>")
    sys_tokens = tokens(SYSTEM)
    out = [f"# Noor inference cost report",
           "",
           f"Generated {date.today().isoformat()} by `scripts/cost_report.py` from the query log.",
           f"Prices: Anthropic pricing page, read **{PRICES_DATE}** "
           "(platform.claude.com/docs/en/about-claude/pricing). Haiku 5.5 rates are for prompts under 100K tokens.",
           "",
           "| Model | Input $/MTok | Output $/MTok | Cache write (5 min) | Cache read |",
           "| --- | --- | --- | --- | --- |"]
    for m, (pi, po, pw, pr) in PRICES.items():
        out.append(f"| {m} | ${pi:g} | ${po:g} | ${pw:g} | ${pr:g} |")
    out += ["| ollama (local) | $0 | $0 | n/a | n/a |", "",
            "Bench: the 20 fixed questions in `evals/bench.txt` (18 answerable, 2 off-topic), "
            "asked once with a cleared answer cache (cold) and then again (repeat).", ""]

    measured = {}
    out += ["## Measured", "",
            "| Model | Queries | Model calls | Avg tokens in | Avg tokens out | $/query | p50 latency | p95 latency |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m in models:
        rows = model_rows(con, m, "bench-cold")
        called = [r for r in rows if r[0] > 0]
        lat = [r[3] for r in rows]
        measured[m] = rows
        out.append(f"| {m} | {len(rows)} | {len(called)} | {statistics.mean(r[0] for r in called):,.0f} | "
                   f"{statistics.mean(r[1] for r in called):,.0f} | {money(statistics.mean(r[2] for r in rows))} | "
                   f"{pct(lat, .5) / 1000:.1f} s | {pct(lat, .95) / 1000:.1f} s |")
    out += ["", "Averages for tokens cover model calls only; $/query and latency cover all 20 questions "
            "(off-topic questions are refused before any model call, for $0).", ""]

    base_model = next((m for m in models if m.startswith("ollama:")), models[0])
    base = [r for r in measured[base_model] if r[0] > 0]
    n_all = len(measured[base_model])
    call_share = len(base) / n_all
    avg_in = statistics.mean(r[0] for r in base)
    avg_out = statistics.mean(r[1] for r in base)
    projected = [m for m in PRICES if m not in models]
    if projected:
        out += ["## Projected for Claude (not yet measured)", "",
                f"No `ANTHROPIC_API_KEY` yet, so Claude is priced from the **{base_model}** token counts above: "
                f"{avg_in:,.0f} in and {avg_out:,.0f} out per model call, on {len(base)} of {n_all} questions. "
                "Claude's tokenizer counts differently (expect roughly ±15%), and Claude may write shorter or longer "
                "answers. Re-run `scripts/bench.py --model claude-haiku` once a key exists, and this section is "
                "replaced by measured rows.", ""]

    def per_query(m, warm: bool) -> float:
        pi, po, pw, pr = PRICES[m]
        s_tok = min(sys_tokens, avg_in)
        cached_part = s_tok * (pr if warm else pw)
        return call_share * ((avg_in - s_tok) * pi + cached_part + avg_out * po) / 1e6

    def no_cache(m) -> float:
        pi, po, _, _ = PRICES[m]
        return call_share * (avg_in * pi + avg_out * po) / 1e6

    out += ["## Cost per query and per month", "",
            "| Model | Basis | $/query | 100 / month | 1,000 / month | 10,000 / month |",
            "| --- | --- | --- | --- | --- | --- |"]
    for m in models:
        c = statistics.mean(r[2] for r in measured[m])
        out.append(f"| {m} | measured | {money(c)} | " + " | ".join(money(c * v) for v in VOLUMES) + " |")
    for m in projected:
        c = no_cache(m)
        out.append(f"| {m} | projected, no caching | {money(c)} | " + " | ".join(money(c * v) for v in VOLUMES) + " |")
    out += ["", f"Local hardware for the Ollama rows: {hardware()}. The local model costs $0 in API fees but "
            "needs a GPU with about 5 GB free, takes ~10 s per answer here (against the PRD's 5 s target for "
            "Haiku), and draws power while it runs.", ""]

    out += ["## Caching savings", "", "### Prompt cache (Claude only)", "",
            f"Noor's system prompt is ~{sys_tokens} tokens, identical on every call, and placed before a cache "
            "breakpoint. It was lengthened past the 512-token minimum, below which Claude silently does not "
            f"cache. That leaves ~{max(0, avg_in - sys_tokens):,.0f} tokens per call of retrieved passages and "
            "question that change each time and can't be cached. The cache lives 5 minutes, so savings depend on "
            "how often queries arrive:", "",
            "| Model | No caching | Cache cold (each call writes) | Cache warm (each call reads) | Saving when warm |",
            "| --- | --- | --- | --- | --- |"]
    for m in PRICES:
        base_c, cold, warm = no_cache(m), per_query(m, False), per_query(m, True)
        out.append(f"| {m} | {money(base_c)} | {money(cold)} ({(cold / base_c - 1) * 100:+.1f}%) | "
                   f"{money(warm)} | **{(1 - warm / base_c) * 100:.1f}%** |")
    out += ["", "Read it this way: in a study session (several questions within 5 minutes) the prompt cache "
            "cuts input cost by the warm figure; at 100 scattered queries a month most calls are cold and "
            "pay the small write premium instead. Measured `cache_read` / `cache_write` tokens are logged per "
            "query and will replace these figures once Claude runs.", "", "### Answer cache (all models)", ""]
    for m in models:
        rep = model_rows(con, m, "bench-repeat")
        cold_rows = measured[m]
        hits = sum(r[5] for r in rep)
        cold_lat = statistics.mean(r[3] for r in cold_rows)
        rep_lat = statistics.mean(r[3] for r in rep) if rep else 0
        out += [f"Measured on {m}: the repeat pass served **{hits} of {len(rep)}** questions from the answer cache "
                f"with no model call. Average latency fell from {cold_lat / 1000:.1f} s to {rep_lat:.0f} ms "
                f"(**{(1 - rep_lat / cold_lat) * 100:.0f}% faster**), and cost on a hit is $0 for every model.", ""]
    out += ["Monthly saving equals the share of questions that repeat. For Claude Haiku 5.5 at 10,000 queries a month:", "",
            "| Repeat rate | Monthly cost (no caching) | With answer cache | Saving |", "| --- | --- | --- | --- |"]
    hk = no_cache("claude-haiku-5-5") * 10_000
    for r in REPEAT_RATES:
        out.append(f"| {r:.0%} | {money(hk)} | {money(hk * (1 - r))} | {r:.0%} |")
    out += ["", "## How to reproduce", "", "```", "python scripts/bench.py --model ollama:qwen2.5:7b",
            "python scripts/bench.py --model claude-haiku     # needs ANTHROPIC_API_KEY",
            "python scripts/bench.py --model claude-sonnet", "python scripts/cost_report.py", "```", ""]
    path = ROOT / "reports" / "cost.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
