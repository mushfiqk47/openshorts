"""AI_PROVIDER=custom: any OpenAI-compatible endpoint (tunnel, vLLM,
llama.cpp server). Config comes from AI_BASE_URL / AI_API_KEY / AI_MODEL."""
import os
from typing import Optional, Tuple

from ai.openai_compat import complete


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
    base = ai_base_url()
    model = model or ai_model()
    if not base or not model:
        raise RuntimeError("AI_PROVIDER=custom needs AI_BASE_URL and AI_MODEL set")
    return complete(base, ai_api_key() or "no-key", model, prompt,
                    system=system, temperature=temperature,
                    max_retries=max_retries, label="custom endpoint")
