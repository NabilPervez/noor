"""One LLMProvider interface; the model is chosen by NOOR_MODEL.

  claude-haiku | claude-sonnet | claude:<model-id> | ollama:<model>
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

CLAUDE_ALIASES = {"claude-haiku": "claude-haiku-5-5", "claude-sonnet": "claude-sonnet-5-5"}
# USD per 1M tokens: (input, output, 5-minute cache write, cache read).
# Source: platform.claude.com/docs/en/about-claude/pricing, read 2026-10-20.
# Haiku 5.5 rates are for prompts up to 100K tokens (Noor's prompts are ~2-4K).
PRICES_DATE = "2026-10-20"
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
}


@dataclass
class Generation:
    text: str
    model: str
    tokens_in: int          # uncached input tokens
    tokens_out: int
    latency_ms: int
    cost_usd: float
    cache_read: int = 0     # input tokens served from the prompt cache
    cache_write: int = 0    # input tokens written to the prompt cache


class LLMProvider(Protocol):
    name: str

    def generate(self, system: str, user: str) -> Generation: ...


def cost(model: str, tokens_in: int, tokens_out: int, cache_write: int = 0, cache_read: int = 0) -> float:
    p_in, p_out, p_w, p_r = PRICES.get(model, (0.0, 0.0, 0.0, 0.0))
    return round((tokens_in * p_in + tokens_out * p_out + cache_write * p_w + cache_read * p_r) / 1_000_000, 8)


class ClaudeProvider:
    def __init__(self, model: str):
        import anthropic  # imported lazily so Ollama-only setups never need a key
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env (see console.anthropic.com).")
        self.client = anthropic.Anthropic()
        self.model = CLAUDE_ALIASES.get(model, model)
        self.name = self.model

    def generate(self, system: str, user: str) -> Generation:
        t0 = time.perf_counter()
        r = self.client.messages.create(
            model=self.model, max_tokens=2000,
            # The system prompt is identical on every call and over the 512-token minimum,
            # so it is cached; the passages and question come after the breakpoint.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": user}])
        text = "".join(b.text for b in r.content if b.type == "text")
        if r.stop_reason == "refusal":
            text = "NOT_FOUND"
        u = r.usage
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        return Generation(text, self.model, u.input_tokens, u.output_tokens,
                          int((time.perf_counter() - t0) * 1000),
                          cost(self.model, u.input_tokens, u.output_tokens, cw, cr), cr, cw)


class OllamaProvider:
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model, self.host, self.name = model, host.rstrip("/"), f"ollama:{model}"

    def generate(self, system: str, user: str) -> Generation:
        t0 = time.perf_counter()
        r = httpx.post(f"{self.host}/api/chat", timeout=600, json={
            "model": self.model, "stream": False, "options": {"temperature": 0.1, "num_ctx": 8192},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        d = r.json()
        return Generation(d["message"]["content"], self.name, d.get("prompt_eval_count", 0),
                          d.get("eval_count", 0), int((time.perf_counter() - t0) * 1000), 0.0)


def get_provider(spec: str, ollama_host: str = "http://localhost:11434") -> LLMProvider:
    if spec.startswith("ollama:"):
        return OllamaProvider(spec.split(":", 1)[1], ollama_host)
    if spec in CLAUDE_ALIASES or spec.startswith("claude"):
        return ClaudeProvider(spec.split(":", 1)[1] if spec.startswith("claude:") else spec)
    raise ValueError(f"unknown model {spec!r}: use claude-haiku, claude-sonnet or ollama:<model>")
