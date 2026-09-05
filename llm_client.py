"""
LLM Client for OpenShorts — drop-in support for Ollama and any OpenAI-compatible base model.

Supports:
  - Local Ollama (default at http://localhost:11434/v1)
  - LM Studio, vLLM, LocalAI, text-generation-webui
  - Remote OpenAI-compatible endpoints (Groq, Together, DeepSeek, OpenAI, etc.)

Uses the `openai` Python library with configurable `base_url`, `api_key`, and `model`.
"""
import json
import os
import re
import time
from typing import Optional, Tuple, List, Dict, Any

import gemini_worker


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2:1b"
DEFAULT_API_KEY = "ollama"


def normalize_base_url(url: Optional[str]) -> str:
    """Normalize base URL so it points to the OpenAI-compatible v1 endpoint."""
    u = (url or "").strip()
    if not u:
        return DEFAULT_BASE_URL
    u = u.rstrip("/")
    # If user provided base URL without /v1 (e.g. http://localhost:11434 or http://127.0.0.1:1234), append /v1
    if not u.endswith("/v1") and not "/v1/" in u:
        if any(h in u for h in ("11434", "1234", "8080", "localhost", "127.0.0.1")):
            u = f"{u}/v1"
    return u


def resolve_llm_base_url(request_headers: Optional[dict] = None) -> str:
    """Resolve base URL from request headers, env, or default to Ollama."""
    if request_headers:
        hdr = {k.lower(): v for k, v in request_headers.items()} if isinstance(request_headers, dict) else {}
        for name in ("x-llm-base-url", "x-base-url", "x-llm-url"):
            if name in hdr and hdr[name] and hdr[name].strip():
                return normalize_base_url(hdr[name])
    env_url = (
        os.environ.get("LLM_BASE_URL")
        or os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
    )
    if env_url and env_url.strip():
        return normalize_base_url(env_url)
    return DEFAULT_BASE_URL


def resolve_llm_model(request_headers: Optional[dict] = None) -> str:
    """Resolve model name from request headers, env, or default."""
    if request_headers:
        hdr = {k.lower(): v for k, v in request_headers.items()} if isinstance(request_headers, dict) else {}
        for name in ("x-llm-model", "x-model"):
            if name in hdr and hdr[name] and hdr[name].strip():
                return hdr[name].strip()
    m = (
        os.environ.get("LLM_MODEL")
        or os.environ.get("OLLAMA_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or os.environ.get("MODEL")
    )
    if m and m.strip():
        return m.strip()
    return DEFAULT_MODEL


def resolve_llm_key(request_headers: Optional[dict] = None) -> str:
    """Resolve API key. Ollama does not require one; defaults to 'ollama'."""
    if request_headers:
        hdr = {k.lower(): v for k, v in request_headers.items()} if isinstance(request_headers, dict) else {}
        for name in ("x-llm-key", "x-llm-api-key", "x-api-key"):
            if name in hdr and hdr[name] and hdr[name].strip():
                return hdr[name].strip()
    k = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if k and k.strip():
        return k.strip()
    return DEFAULT_API_KEY


def resolve_llm_config(request_headers: Optional[dict] = None) -> Tuple[str, str, str]:
    """Returns (base_url, model, api_key)."""
    return (
        resolve_llm_base_url(request_headers),
        resolve_llm_model(request_headers),
        resolve_llm_key(request_headers),
    )


def is_ollama(base_url: Optional[str] = None) -> bool:
    """True if base_url appears to point to an Ollama server."""
    url = (base_url or resolve_llm_base_url()).lower()
    return "11434" in url or "ollama" in url


def _get_client(base_url: Optional[str] = None, api_key: Optional[str] = None):
    """Lazy OpenAI client initialized with base_url and api_key."""
    from openai import OpenAI
    url = normalize_base_url(base_url)
    key = (api_key or resolve_llm_key() or DEFAULT_API_KEY).strip()
    return OpenAI(base_url=url, api_key=key)


def _strip_and_parse(text: str) -> dict:
    """Robust JSON extraction mirroring gemini_worker._parse_json_response_text."""
    if not text or not text.strip():
        raise ValueError("LLM returned empty response body.")
    return gemini_worker._parse_json_response_text(text)


def fetch_available_models(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Fetch available models from the OpenAI-compatible endpoint or native Ollama.
    Returns list of dicts with at least 'id' and 'name'.
    """
    import httpx

    target_url = normalize_base_url(base_url)
    key = (api_key or resolve_llm_key() or DEFAULT_API_KEY).strip()
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    models: List[Dict[str, Any]] = []

    # 1. Try standard OpenAI /v1/models endpoint
    v1_models_url = f"{target_url}/models"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(v1_models_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", []) if isinstance(data, dict) else []
                for item in items:
                    mid = item.get("id") or ""
                    if mid:
                        models.append({
                            "id": mid,
                            "name": mid,
                            "owned_by": item.get("owned_by", ""),
                        })
                if models:
                    return models
    except Exception:
        pass

    # 2. If it's Ollama or OpenAI /models failed, try native Ollama /api/tags
    root_url = re.sub(r"/v1/?$", "", target_url)
    ollama_tags_url = f"{root_url}/api/tags"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(ollama_tags_url)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("models", []) if isinstance(data, dict) else []
                for m in raw_models:
                    name = m.get("name") or m.get("model") or ""
                    if name:
                        models.append({
                            "id": name,
                            "name": name,
                            "size": m.get("size", 0),
                            "details": m.get("details", {}),
                        })
                if models:
                    return models
    except Exception:
        pass

    return models


def call_llm(
    prompt: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 3,
) -> Tuple[dict, Optional[dict]]:
    """
    Execute chat completion and parse JSON output.
    Returns (parsed_dict, cost_dict).
    Works across Ollama, LM Studio, vLLM, OpenAI, Groq, DeepSeek, etc.
    """
    base_url = normalize_base_url(base_url)
    model = model or resolve_llm_model()
    api_key = api_key or resolve_llm_key()

    client = _get_client(base_url=base_url, api_key=api_key)

    sys_content = system or (
        "You are a senior short-form video editor. "
        "You MUST return ONLY valid JSON matching the schema requested. "
        "Do not include explanation, preamble, markdown code blocks, or extra text."
    )

    messages = [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": prompt},
    ]

    last_err = None
    use_json_mode = True

    for attempt in range(1, max_retries + 1):
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096,
            }
            if use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            try:
                resp = client.chat.completions.create(**kwargs)
            except Exception as req_err:
                msg_lower = str(req_err).lower()
                if use_json_mode and any(term in msg_lower for term in ("response_format", "json_object", "unsupported", "invalid parameter")):
                    print(f"⚠️ Model/server does not support response_format=json_object; falling back to prompt-guided JSON.")
                    use_json_mode = False
                    kwargs.pop("response_format", None)
                    resp = client.chat.completions.create(**kwargs)
                else:
                    raise req_err

            if not resp.choices:
                raise ValueError("LLM response contained no choices")

            text = resp.choices[0].message.content or ""
            if not text.strip():
                text = getattr(resp.choices[0].message, "reasoning", "") or ""
                if not text.strip():
                    raise ValueError("LLM returned empty message content")

            parsed = _strip_and_parse(text)

            # Build usage statistics
            usage = getattr(resp, "usage", None)
            if usage is not None:
                cost = {
                    "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "thinking_tokens": 0,
                    "total_cost": 0.0,
                    "model": model,
                    "provider": "ollama" if is_ollama(base_url) else "openai_compatible",
                }
            else:
                cost = {
                    "input_tokens": len(prompt) // 4,
                    "output_tokens": len(text) // 4,
                    "total_cost": 0.0,
                    "model": model,
                    "provider": "ollama" if is_ollama(base_url) else "openai_compatible",
                }

            return parsed, cost

        except Exception as e:
            last_err = e
            msg = str(e)
            msg_lower = msg.lower()

            # Connection refused (Ollama or local server not running)
            if any(term in msg_lower for term in ("connection refused", "connecterror", "connection error", "failed to connect", "target machine actively refused")):
                raise RuntimeError(
                    f"Could not connect to LLM server at '{base_url}'. "
                    f"If using Ollama, ensure it is running: 'ollama serve' or 'ollama run {model}'."
                ) from e

            # Model not found (404)
            if "404" in msg or "not found" in msg_lower:
                if is_ollama(base_url):
                    raise ValueError(
                        f"Model '{model}' not found in Ollama at '{base_url}'. "
                        f"Please pull it first: 'ollama pull {model}' (or choose one from your installed models)."
                    ) from e
                raise ValueError(f"Model '{model}' not found at '{base_url}'.") from e

            # Authentication error (401/403)
            if "401" in msg or "403" in msg or "unauthorized" in msg_lower:
                raise ValueError(
                    f"Authentication failed for LLM at '{base_url}'. Please check your API key."
                ) from e

            # Rate limit or transient error retry
            transient = any(tok in msg_lower for tok in (
                "429", "rate limit", "500", "502", "503", "504", "timeout", "overloaded", "temporarily"
            ))
            if attempt == max_retries or not transient:
                raise

            wait = 2 * attempt
            print(f"⚠️ LLM transient error (attempt {attempt}/{max_retries}), retrying in {wait}s: {msg[:180]}")
            time.sleep(wait)

    raise last_err or RuntimeError("LLM call failed after retries")


def run_llm_score(
    prompt: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[dict, Optional[dict]]:
    """Score pass via LLM (temperature 0.2, deterministic/precise)."""
    return call_llm(prompt, base_url=base_url, api_key=api_key, model=model, temperature=0.2)


def run_llm_detail(
    prompt: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[dict, Optional[dict]]:
    """Detail pass via LLM (temperature 0.7, creative copy)."""
    return call_llm(prompt, base_url=base_url, api_key=api_key, model=model, temperature=0.7)


def validate_llm(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[bool, str]:
    """Lightweight validation: check model list or send 1-token test prompt."""
    url = normalize_base_url(base_url)
    target_model = model or resolve_llm_model()
    try:
        models = fetch_available_models(base_url=url, api_key=api_key, timeout=5.0)
        if models:
            model_names = [m["id"] for m in models]
            if target_model in model_names or any(target_model in m for m in model_names):
                return True, f"Connected to {url}. Model '{target_model}' ready."
            return True, f"Connected to {url}. Found {len(models)} model(s): {', '.join(model_names[:3])}..."
    except Exception:
        pass

    try:
        client = _get_client(base_url=url, api_key=api_key)
        resp = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": 'Return JSON: {"ok": true}'}],
            max_tokens=20,
        )
        _ = resp.choices[0].message.content
        return True, f"Successfully connected to '{target_model}' at {url}"
    except Exception as e:
        return False, str(e)[:300]


# Backwards-compatibility aliases
call_openrouter = call_llm
run_openrouter_score = run_llm_score
run_openrouter_detail = run_llm_detail
