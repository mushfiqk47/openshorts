"""Shared transport for the OpenAI-compatible stages (custom endpoint, Ollama).

The former custom_client.py and ollama_client.py were byte-for-byte the same
call apart from endpoint config: message construction, the reasoning-safe
no-json_object contract, the retry loop, the empty-content/reasoning-field
fallback, and the zero-cost accounting all lived duplicated in both. One
implementation lives here; ai/custom.py and ai/ollama.py resolve their
endpoint config and delegate.
"""
import time
from typing import Optional, Tuple

import gemini_worker

SYSTEM_JSON_PROMPT = (
    "You are a senior short-form video editor. "
    "You MUST return ONLY valid JSON, no markdown, no explanation, no code fences."
)


def usage_cost(model: str, usage) -> dict:
    """The zero-priced cost stub every OpenAI-compatible stage returns. Shape
    matches gemini_worker's cost analysis so the aggregation stays shared."""
    if usage is not None:
        return {
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "thinking_tokens": 0,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
            "model": model,
            "price_estimated": False,
        }
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "thinking_tokens": 0,
        "input_cost": 0.0,
        "output_cost": 0.0,
        "total_cost": 0.0,
        "model": model,
        "price_estimated": False,
    }


def complete(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 2,
    label: str = "endpoint",
) -> Tuple[dict, Optional[dict]]:
    """One chat completion against an OpenAI-compatible endpoint.

    Reasoning-safe by design: NO response_format (reasoning models burn their
    budget thinking when JSON mode is forced and return empty content), a
    large token ceiling, and the tolerant JSON extractor as the last step.
    Returns (parsed, cost)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages = [{"role": "system", "content": system or SYSTEM_JSON_PROMPT},
                {"role": "user", "content": prompt}]

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=16384,
            )
            if not resp.choices:
                raise ValueError(f"{label} response has no choices")
            text = resp.choices[0].message.content or ""
            if not text.strip():
                # Reasoning-heavy models can leave content empty; the raw
                # thinking stream still usually ends in the JSON block.
                text = getattr(resp.choices[0].message, "reasoning", "") or ""
            if not text.strip():
                raise ValueError(f"{label} returned empty content")
            parsed = gemini_worker._parse_json_response_text(text)
            return parsed, usage_cost(model, getattr(resp, "usage", None))
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                print(f"⚠️ {label} attempt {attempt}/{max_retries} failed ({e}) — retrying")
                time.sleep(1)
    raise RuntimeError(f"{label} call failed after {max_retries} attempts: {last_err}")
