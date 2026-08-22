"""
OpenRouter client for OpenShorts — drop-in alternative to Gemini for clip selection.

Uses the OpenAI-compatible API at https://openrouter.ai/api/v1 with the
`openai` Python library (already installed). Supports any model on OpenRouter;
designed for free-tier models like:

  - meta-llama/llama-3.1-8b-instruct:free
  - google/gemma-2-9b-it:free
  - qwen/qwen-2.5-7b-instruct:free
  - deepseek/deepseek-r1:free
  - openai/gpt-oss-20b:free

The user provides the key via:
  - header  X-OpenRouter-Key  (dashboard sends it)
  - env     OPENROUTER_API_KEY
  - header  X-Gemini-Key that looks like sk-or-v1-* (auto-detect)

Model selection:
  - header X-OpenRouter-Model or env OPENROUTER_MODEL or env GEMINI_MODEL
  - fallback: meta-llama/llama-3.1-8b-instruct:free

The prompt templates are reused verbatim from gemini_worker.py so behavior
stays identical; only the transport changes (chat.completions with json_object).
"""
import json
import os
import time
from typing import Optional, Tuple

import gemini_worker


DEFAULT_MODEL = "z-ai/glm-5.2:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Live free models as of 2026-08-22 (fetched from /api/v1/models, 18 free).
# The old list (meta-llama:free, gemma-2:free, qwen:free, gpt-oss:free) is now 404 paid-only.
# This list is the fallback when the live fetch fails; the frontend auto-detects via /api/openrouter/models.
FREE_MODELS = [
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "liquid/lfm-2.5-2.6b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "dots-studio/dots-3-note-preview:free",
    "cohere/north-mini-code:free",
    "thinkingmachines/inkling-small:free",
    "poolside/laguna-xs-2.1:free",
]


def is_openrouter_key(key: Optional[str]) -> bool:
    if not key:
        return False
    k = key.strip()
    return k.startswith("sk-or-v1-") or k.startswith("sk-or-")


def resolve_openrouter_key(request_headers: Optional[dict] = None) -> Optional[str]:
    """Check headers then env for an OpenRouter key. Returns None if not found."""
    if request_headers:
        # Starlette headers are case-insensitive, but dict lookup is not.
        hdr = {k.lower(): v for k, v in request_headers.items()} if isinstance(request_headers, dict) else {}
        # Try explicit OpenRouter header first
        for name in ("x-openrouter-key", "x-openrouter-api-key"):
            if name in hdr and hdr[name]:
                return hdr[name].strip()
        # Auto-detect: a Gemini header that is actually an OpenRouter key
        gkey = hdr.get("x-gemini-key") or hdr.get("x-gemini-api-key")
        if is_openrouter_key(gkey):
            return gkey.strip()
    # Env fallback
    env_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    # Also check Gemini env if it looks like OpenRouter
    g_env = os.environ.get("GEMINI_API_KEY") or ""
    if is_openrouter_key(g_env):
        return g_env.strip()
    return None


def resolve_openrouter_model(request_headers: Optional[dict] = None) -> str:
    """Resolve model name, same precedence as key."""
    if request_headers:
        hdr = {k.lower(): v for k, v in request_headers.items()} if isinstance(request_headers, dict) else {}
        for name in ("x-openrouter-model", "x-openrouter_model"):
            if name in hdr and hdr[name]:
                return hdr[name].strip()
    # Env: prefer OPENROUTER_MODEL, then GEMINI_MODEL if it looks like openrouter path
    m = os.environ.get("OPENROUTER_MODEL") or os.environ.get("OPENROUTER-model")
    if m and m.strip():
        return m.strip()
    g_model = os.environ.get("GEMINI_MODEL") or ""
    if "/" in g_model and ":" in g_model:
        # looks like openrouter "vendor/model:free"
        return g_model.strip()
    # Also check generic MODEL var
    m2 = os.environ.get("MODEL") or ""
    if m2 and "/" in m2:
        return m2.strip()
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _get_openai_client(api_key: str):
    """Lazy OpenAI client pointed at OpenRouter."""
    from openai import OpenAI

    # OpenRouter recommends Referer + Title headers for ranking; not required.
    headers = {}
    referer = os.environ.get("OPENROUTER_REFERER") or "http://localhost:5175"
    title = os.environ.get("OPENROUTER_TITLE") or "OpenShorts"
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE,
        default_headers=headers if headers else None,
    )


def _strip_and_parse(text: str) -> dict:
    """Robust JSON extraction mirroring gemini_worker._parse_json_response_text."""
    if not text:
        raise ValueError("OpenRouter returned empty response body.")
    # Reuse gemini_worker helpers (same repair logic)
    return gemini_worker._parse_json_response_text(text)


def call_openrouter(
    prompt: str,
    api_key: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 3,
) -> Tuple[dict, Optional[dict]]:
    """
    Single chat completion that forces JSON output.
    Returns (parsed_dict, cost_analysis_or_None).
    Raises on failure after retries.
    """
    model = model or resolve_openrouter_model()
    client = _get_openai_client(api_key)

    messages = []
    # System instruction helps free models stay in JSON mode
    sys_content = system or (
        "You are a senior short-form video editor. "
        "You MUST return ONLY valid JSON, no markdown, no explanation, no code fences."
    )
    messages.append({"role": "system", "content": sys_content})
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
            # Extract text
            if not resp.choices:
                raise ValueError("OpenRouter response has no choices")
            text = resp.choices[0].message.content or ""
            if not text.strip():
                # Some models return thinking in reasoning field
                text = getattr(resp.choices[0].message, "reasoning", "") or ""
                if not text.strip():
                    raise ValueError("OpenRouter returned empty content")
            parsed = _strip_and_parse(text)

            # Build cost stub (free models cost 0; keep shape compatible with gemini)
            usage = getattr(resp, "usage", None)
            cost = None
            if usage is not None:
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
            else:
                cost = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_cost": 0.0,
                    "model": model,
                }

            # Validate that common expected keys exist, otherwise retry extraction
            return parsed, cost

        except Exception as e:
            last_err = e
            msg = str(e)
            # Surface auth errors clearly — don't retry and don't misclassify as model-not-found
            if "401" in msg or "403" in msg or "User not found" in msg or "invalid" in msg.lower() and "api key" in msg.lower():
                raise ValueError(
                    "OpenRouter authentication failed (401). Your API key is invalid or not found. "
                    "Get a free key at https://openrouter.ai/keys and paste it as sk-or-v1-..."
                ) from e
            # Model not found -> try fallback model once (only on explicit 404/model errors, not auth)
            if "404" in msg or "No endpoints found" in msg or ("not found" in msg.lower() and "User not found" not in msg):
                if attempt == 1 and model != DEFAULT_MODEL:
                    print(f"⚠️ OpenRouter model '{model}' not found, retrying with {DEFAULT_MODEL}")
                    model = DEFAULT_MODEL
                    continue
                raise ValueError(f"OpenRouter model '{model}' not found. Try one of: {', '.join(FREE_MODELS[:4])}") from e

            # Free-tier 429: shared pool rate-limited — rotate to next free model instead of hammering same one
            if "429" in msg or "rate limit" in msg.lower() or "rate-limited" in msg.lower():
                # Build rotation list: start after current model, wrap around
                try:
                    idx = FREE_MODELS.index(model) if model in FREE_MODELS else -1
                except ValueError:
                    idx = -1
                # Try next 3 models in the free list that aren't the current one
                tried = set([model])
                for off in range(1, min(4, len(FREE_MODELS))):
                    nxt = FREE_MODELS[(idx + off) % len(FREE_MODELS)] if idx >= 0 else FREE_MODELS[off % len(FREE_MODELS)]
                    if nxt in tried:
                        continue
                    tried.add(nxt)
                    print(f"⚠️ {model} rate-limited (429) — trying next free model {nxt} (attempt {attempt})")
                    model = nxt
                    # Respect Retry-After if present (default 2s)
                    import re as _re
                    m = _re.search(r"retry_after_seconds.*?(\d+)", msg)
                    wait = int(m.group(1)) if m else 2
                    time.sleep(wait)
                    break
                else:
                    # No more fallbacks, treat as transient retry
                    if attempt == max_retries:
                        raise ValueError(
                            "All free models are rate-limited right now (shared pool). "
                            "Wait 20s and retry, or add your own provider key at https://openrouter.ai/settings/integrations "
                            "to get higher limits, or switch to a Gemini key (AIza...) for no rate limits."
                        ) from e
                    wait = 2 * attempt
                    print(f"⚠️ OpenRouter rate-limited (attempt {attempt}/{max_retries}), retrying in {wait}s: {msg[:180]}")
                    time.sleep(wait)
                continue

            # Other transient 5xx / empty body
            transient = any(tok in msg for tok in (
                "529", "503", "500", "502", "504",
                "overloaded", "timeout", "empty", "choices",
                "Failed to parse", "temporarily"
            ))
            if attempt == max_retries or not transient:
                raise
            wait = 2 * attempt
            print(f"⚠️ OpenRouter transient error (attempt {attempt}/{max_retries}), retrying in {wait}s: {msg[:200]}")
            time.sleep(wait)

    raise last_err or RuntimeError("OpenRouter call failed")


def run_openrouter_score(
    prompt: str,
    api_key: str,
    model: Optional[str] = None,
) -> Tuple[dict, Optional[dict]]:
    """Score pass via OpenRouter (temperature 0.2, precise)."""
    return call_openrouter(prompt, api_key, model=model, temperature=0.2)


def run_openrouter_detail(
    prompt: str,
    api_key: str,
    model: Optional[str] = None,
) -> Tuple[dict, Optional[dict]]:
    """Detail pass via OpenRouter (temperature 0.7, creative copy)."""
    return call_openrouter(prompt, api_key, model=model, temperature=0.7)


def should_use_openrouter(request_headers=None) -> bool:
    """True when an OpenRouter key is configured (header or env)."""
    return resolve_openrouter_key(request_headers) is not None


def get_effective_ai_provider(request_headers=None) -> str:
    """'openrouter' when openrouter key present, else 'gemini'."""
    if should_use_openrouter(request_headers):
        return "openrouter"
    return "gemini"


# ---------------------------------------------------------------------------
# Simple health check for the API key — useful for the settings UI / preflight
# ---------------------------------------------------------------------------
def validate_key(api_key: str) -> tuple[bool, str]:
    """Lightweight validation: try a 1-token completion. Returns (ok, message)."""
    if not api_key or not api_key.strip():
        return False, "API key is empty"
    if not is_openrouter_key(api_key):
        # Could still be valid if user pasted a non-standard key; try anyway
        pass
    try:
        client = _get_openai_client(api_key.strip())
        # Cheap call: list models is cheaper and doesn't cost tokens, but not all
        # keys have that permission; try models.list first, fall back to chat.
        try:
            client.models.list()
            return True, "Key valid (models.list succeeded)"
        except Exception:
            pass
        # Fallback: tiny chat
        resp = client.chat.completions.create(
            model=resolve_openrouter_model(),
            messages=[{"role": "user", "content": "Say ok in JSON: {\"ok\": true}"}],
            response_format={"type": "json_object"},
            max_tokens=10,
        )
        _ = resp.choices[0].message.content
        return True, "Key valid"
    except Exception as e:
        return False, str(e)[:300]


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Test OpenRouter connection")
    p.add_argument("--key", default=os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--prompt", default='Return JSON: {"hello": "world"}')
    args = p.parse_args()
    if not args.key:
        print("Provide --key or set OPENROUTER_API_KEY")
        raise SystemExit(1)
    print(f"Testing model={args.model} ...")
    parsed, cost = call_openrouter(args.prompt, args.key, model=args.model)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    print("cost:", cost)
