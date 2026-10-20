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
# USD per 1M tokens (input, output). Anthropic pricing as of 2026-10-06; re-check in Sprint 2.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}


@dataclass
class Generation:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float


class LLMProvider(Protocol):
    name: str

    def generate(self, system: str, user: str) -> Generation: ...


def cost(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = PRICES.get(model, (0.0, 0.0))
    return round((tokens_in * p_in + tokens_out * p_out) / 1_000_000, 8)


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
            model=self.model, max_tokens=2000, system=system,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": user}])
        text = "".join(b.text for b in r.content if b.type == "text")
        if r.stop_reason == "refusal":
            text = "NOT_FOUND"
        tin, tout = r.usage.input_tokens, r.usage.output_tokens
        return Generation(text, self.model, tin, tout, int((time.perf_counter() - t0) * 1000),
                          cost(self.model, tin, tout))


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
