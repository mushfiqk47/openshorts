"""Ollama (local) AI stage — same contract as openrouter_client.call_openrouter.

Talks to Ollama's OpenAI-compatible endpoint (http://localhost:11434/v1) so the
clip-selection stages can run fully offline on a local model. Select it with
AI_PROVIDER=ollama and pick the model with OLLAMA_MODEL (default
lfm3-vl:2b-q4_K_M — a vision model, though the selection prompts are
text-only). Returns (parsed_dict, cost) exactly like call_openrouter, so the
cost accounting and JSON repair paths stay shared.
"""
import os
import time
from typing import Optional, Tuple

import gemini_worker


def ollama_url() -> str:
    return (os.environ.get("OLLAMA_URL") or "http://localhost:11434").strip().rstrip("/")


def ollama_model() -> str:
    return (os.environ.get("OLLAMA_MODEL") or "lfm3-vl:2b-q4_K_M").strip()


def call_ollama(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 2,
) -> Tuple[dict, Optional[dict]]:
    """One local chat completion that forces JSON output. Raises on failure."""
    from openai import OpenAI

    model = model or ollama_model()
    client = OpenAI(api_key="ollama", base_url=ollama_url() + "/v1")

    messages = [{"role": "system", "content": system or (
        "You are a senior short-form video editor. "
        "You MUST return ONLY valid JSON, no markdown, no explanation, no code fences."
    )}, {"role": "user", "content": prompt}]

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            # NO response_format here: reasoning models (lfm3-vl et al) spend
            # their token budget thinking inside the hidden reasoning field
            # when JSON mode is forced, hit the cap and return empty content
            # (finish_reason=length). Free-form output + the tolerant JSON
            # extractor below gets both reasoning and plain models through.
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=16384,
            )
            if not resp.choices:
                raise ValueError("Ollama response has no choices")
            text = resp.choices[0].message.content or ""
            if not text.strip():
                # Reasoning-heavy models can leave content empty; the raw
                # thinking stream still usually ends in the JSON block.
                text = getattr(resp.choices[0].message, "reasoning", "") or ""
            if not text.strip():
                raise ValueError("Ollama returned empty content")
            parsed = gemini_worker._parse_json_response_text(text)
            usage = getattr(resp, "usage", None)
            cost = {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "thinking_tokens": 0,
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0,
                "model": model,
                "price_estimated": False,
            }
            return parsed, cost
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                print(f"⚠️ ollama attempt {attempt}/{max_retries} failed ({e}) — retrying")
                time.sleep(1)
    raise RuntimeError(f"Ollama call failed after {max_retries} attempts: {last_err}")
