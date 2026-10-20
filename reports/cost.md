# Noor inference cost report

Generated 2026-10-20 by `scripts/cost_report.py` from the query log.
Prices: Anthropic pricing page, read **2026-10-20** (platform.claude.com/docs/en/about-claude/pricing). Haiku 5.5 rates are for prompts under 100K tokens.

| Model | Input $/MTok | Output $/MTok | Cache write (5 min) | Cache read |
| --- | --- | --- | --- | --- |
| claude-haiku-5-5 | $0.1 | $0.5 | $0.125 | $0.01 |
| claude-sonnet-5-5 | $2 | $10 | $2.5 | $0.1 |
| ollama (local) | $0 | $0 | n/a | n/a |

Bench: the 20 fixed questions in `evals/bench.txt` (18 answerable, 2 off-topic), asked once with a cleared answer cache (cold) and then again (repeat).

## Measured

| Model | Queries | Model calls | Avg tokens in | Avg tokens out | $/query | p50 latency | p95 latency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ollama:qwen2.5:7b | 20 | 17 | 2,806 | 210 | $0 | 9.4 s | 14.5 s |

Averages for tokens cover model calls only; $/query and latency cover all 20 questions (off-topic questions are refused before any model call, for $0).

## Projected for Claude (not yet measured)

No `ANTHROPIC_API_KEY` yet, so Claude is priced from the **ollama:qwen2.5:7b** token counts above: 2,806 in and 210 out per model call, on 17 of 20 questions. Claude's tokenizer counts differently (expect roughly ±15%), and Claude may write shorter or longer answers. Re-run `scripts/bench.py --model claude-haiku` once a key exists, and this section is replaced by measured rows.

## Cost per query and per month

| Model | Basis | $/query | 100 / month | 1,000 / month | 10,000 / month |
| --- | --- | --- | --- | --- | --- |
| ollama:qwen2.5:7b | measured | $0 | $0 | $0 | $0 |
| claude-haiku-5-5 | projected, no caching | $0.000328 | $0.0328 | $0.3278 | $3.28 |
| claude-sonnet-5-5 | projected, no caching | $0.006556 | $0.6556 | $6.56 | $65.56 |

Local hardware for the Ollama rows: NVIDIA GeForce RTX 2070 GPU, Intel(R) Core(TM) i9-9900K CPU @ 3.60GHz, 32 GB RAM. The local model costs $0 in API fees but needs a GPU with about 5 GB free, takes ~10 s per answer here (against the PRD's 5 s target for Haiku), and draws power while it runs.

## Caching savings

### Prompt cache (Claude only)

Noor's system prompt is ~629 tokens, identical on every call, and placed before a cache breakpoint. It was lengthened past the 512-token minimum, below which Claude silently does not cache. That leaves ~2,177 tokens per call of retrieved passages and question that change each time and can't be cached. The cache lives 5 minutes, so savings depend on how often queries arrive:

| Model | No caching | Cache cold (each call writes) | Cache warm (each call reads) | Saving when warm |
| --- | --- | --- | --- | --- |
| claude-haiku-5-5 | $0.000328 | $0.000341 (+4.1%) | $0.000280 | **14.7%** |
| claude-sonnet-5-5 | $0.006556 | $0.006824 (+4.1%) | $0.005541 | **15.5%** |

Read it this way: in a study session (several questions within 5 minutes) the prompt cache cuts input cost by the warm figure; at 100 scattered queries a month most calls are cold and pay the small write premium instead. Measured `cache_read` / `cache_write` tokens are logged per query and will replace these figures once Claude runs.

### Answer cache (all models)

Measured on ollama:qwen2.5:7b: the repeat pass served **20 of 20** questions from the answer cache with no model call. Average latency fell from 8.9 s to 3 ms (**100% faster**), and cost on a hit is $0 for every model.

Monthly saving equals the share of questions that repeat. For Claude Haiku 5.5 at 10,000 queries a month:

| Repeat rate | Monthly cost (no caching) | With answer cache | Saving |
| --- | --- | --- | --- |
| 10% | $3.28 | $2.95 | 10% |
| 25% | $3.28 | $2.46 | 25% |
| 50% | $3.28 | $1.64 | 50% |

## How to reproduce

```
python scripts/bench.py --model ollama:qwen2.5:7b
python scripts/bench.py --model claude-haiku     # needs ANTHROPIC_API_KEY
python scripts/bench.py --model claude-sonnet
python scripts/cost_report.py
```
