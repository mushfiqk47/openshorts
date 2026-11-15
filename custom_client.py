"""Custom OpenAI-compatible AI stage — same contract as openrouter_client.

AI_PROVIDER=custom sends the clip-selection stages to any OpenAI-compatible
chat endpoint instead of OpenRouter/Gemini/Ollama:
  AI_BASE_URL  e.g. https://my-tunnel.trycloudflare.com/v1
  AI_API_KEY   bearer token the endpoint expects
  AI_MODEL     model id served by that endpoint

Reasoning-safe by design: no response_format (reasoning models burn their
budget thinking when JSON mode is forced and return empty content), a large
token ceiling, and the tolerant JSON extractor as the last step.
"""
import os
import time
from typing import Optional, Tuple

import gemini_worker


def ai_base_url() -> str:
    return (os.environ.get("AI_BASE_URL") or "").strip().rstrip("/")


def ai_api_key() -> str:
    return (os.environ.get("AI_API_KEY") or "").strip()


def ai_model() -> str:
    return (os.environ.get("AI_MODEL") or "").strip()


def call_custom(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 2,
) -> Tuple[dict, Optional[dict]]:
    """One chat completion against AI_BASE_URL. Returns (parsed, cost)."""
    from openai import OpenAI

    base = ai_base_url()
    model = model or ai_model()
    if not base or not model:
        raise RuntimeError("AI_PROVIDER=custom needs AI_BASE_URL and AI_MODEL set")
    client = OpenAI(api_key=ai_api_key() or "no-key", base_url=base)

    messages = [{"role": "system", "content": system or (
        "You are a senior short-form video editor. "
        "You MUST return ONLY valid JSON, no markdown, no explanation, no code fences."
    )}, {"role": "user", "content": prompt}]

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
                raise ValueError("response has no choices")
            text = resp.choices[0].message.content or ""
            if not text.strip():
                # Reasoning-heavy models can leave content empty; the raw
                # thinking stream still usually ends in the JSON block.
                text = getattr(resp.choices[0].message, "reasoning", "") or ""
            if not text.strip():
                raise ValueError("endpoint returned empty content")
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
                print(f"⚠️ custom endpoint attempt {attempt}/{max_retries} failed ({e}) — retrying")
                time.sleep(1)
    raise RuntimeError(f"custom endpoint call failed after {max_retries} attempts: {last_err}")
