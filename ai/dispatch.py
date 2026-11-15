"""The provider dispatch seam (CLAUDE.md rule 2).

AI_PROVIDER picks custom | ollama | openrouter | gemini; 'auto' resolves to
OpenRouter when a key is configured, else Gemini. Stage call sites call
_run_ai_stage and never import a client module directly. Moved verbatim from
main.py (which re-imports the names).
"""
import os


def _use_openrouter() -> bool:
    """True when an OpenRouter key is configured (env or mirrored from request)."""
    k = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY") or "").strip()
    if k:
        return True
    # Also accept a GEMINI_API_KEY that looks like an OpenRouter key (dashboard single field)
    g = (os.environ.get("GEMINI_API_KEY") or "").strip()
    return g.startswith("sk-or-v1-") or g.startswith("sk-or-")


def _openrouter_key() -> str:
    k = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY") or "").strip()
    if k:
        return k
    return (os.environ.get("GEMINI_API_KEY") or "").strip()


def _openrouter_model() -> str:
    return (
        os.environ.get("OPENROUTER_MODEL")
        or os.environ.get("GEMINI_MODEL")
        or "openrouter/free"
    ).strip() or "openrouter/free"


def _ai_provider() -> str:
    """Which service runs the clip-selection stages: custom | ollama |
    openrouter | gemini. AI_PROVIDER pins the choice explicitly; 'auto'
    resolves to OpenRouter when a key is configured (env or mirrored from
    request), else Gemini. 'custom' needs AI_BASE_URL + AI_MODEL and can point
    at any OpenAI-compatible endpoint (tunnel, vLLM, llama.cpp server).
    """
    p = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    if p in ("custom", "ollama", "openrouter", "gemini"):
        return p
    return "openrouter" if _use_openrouter() else "gemini"


def _run_ai_stage(prompt: str, mode: str) -> tuple[dict, dict | None]:
    """One AI call — score or detail — returning (parsed, cost)."""
    # score = precise (0.2), detail = creative (0.7)
    temp = 0.2 if mode == "score" else 0.7
    if _ai_provider() == "custom":
        from ai import custom
        return custom.call_custom(prompt, temperature=temp)
    if _ai_provider() == "ollama":
        from ai import ollama
        return ollama.call_ollama(prompt, temperature=temp)
    from ai import openrouter as openrouter_client

    key = _openrouter_key()
    model = _openrouter_model()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    parsed, cost = openrouter_client.call_openrouter(prompt, api_key=key, model=model, temperature=temp)
    return parsed, cost
