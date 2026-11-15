"""AI_PROVIDER=ollama: the clip-selection stages run fully offline on a
local model via Ollama's OpenAI-compatible endpoint. Model: OLLAMA_MODEL
(default lfm3-vl:2b-q4_K_M)."""
import os
from typing import Optional, Tuple

from ai.openai_compat import complete


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
    return complete(ollama_url() + "/v1", "ollama", model or ollama_model(), prompt,
                    system=system, temperature=temperature,
                    max_retries=max_retries, label="Ollama")
