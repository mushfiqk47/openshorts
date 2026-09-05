"""
Deprecated: OpenRouter has been removed in favor of Ollama and OpenAI-compatible models.
This module is a compatibility shim redirecting to llm_client.py.
"""
from llm_client import (
    call_llm as call_openrouter,
    run_llm_score as run_openrouter_score,
    run_llm_detail as run_openrouter_detail,
    validate_llm as validate_key,
    resolve_llm_key as resolve_openrouter_key,
    resolve_llm_model as resolve_openrouter_model,
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
)

def is_openrouter_key(key):
    return False

def should_use_openrouter(request_headers=None):
    return False

def get_effective_ai_provider(request_headers=None):
    return "ollama"
