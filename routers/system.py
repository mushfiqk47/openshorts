"""System routes: liveness, client config, .env sync, model discovery.

Zero app-internal dependencies beyond `config` — the first cluster behind the
routers/ seam. Interface: `router` only.
"""

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import env_manager as _envm
from config import BILLING_ENABLED, DISABLE_YOUTUBE_URL, JOB_RETENTION_SECONDS

if BILLING_ENABLED:
    import cloud
else:
    cloud = None

router = APIRouter()


@router.get("/health")
async def health():
    """Lightweight liveness probe for uptime monitoring / Coolify health checks."""
    return {"status": "ok"}


@router.get("/api/config")
async def get_config():
    return {
        "youtubeUrlEnabled": not DISABLE_YOUTUBE_URL,
        "billingEnabled": BILLING_ENABLED,
        "googleAuthEnabled": bool(BILLING_ENABLED and cloud.settings.google_auth_enabled),
        "jobRetentionSeconds": JOB_RETENTION_SECONDS,
        "llmProvider": os.environ.get("LLM_PROVIDER", "ollama"),
        "defaultLlmModel": os.environ.get("LLM_MODEL", "llama3.2:1b"),
        "defaultLlmBaseUrl": os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
    }


# ---- Env-file sync (project follows .env, dashboard writes it) --------------


@router.get("/api/env")
async def get_env():
    """Return the live env file snapshot (secrets masked). The file is the
    source of truth — a manual edit is returned on the next GET without a
    restart, and the dashboard's PUT persists through restarts."""
    # Reload file into process env so a manual edit is seen live (project follows .env)
    try:
        from dotenv import load_dotenv as _ld
        _ld(str(_envm.ENV_PATH), override=True)
        # If the file changed GPU-relevant keys, drop memoised probes so next
        # job sees the new value without a restart
        import ffmpeg_utils as _fu
        _fu.reset_encoder_cache()
    except Exception:
        pass
    masked, secrets_set, raw = _envm.masked_snapshot()
    return {
        "env": masked,
        "secretsSet": secrets_set,
        "allowed": sorted(_envm.ALLOWED_ENV),
        "fileExists": _envm.env_file_exists(),
        "path": str(_envm.ENV_PATH),
    }


class EnvUpdateBody(BaseModel):
    updates: Dict[str, Any]


@router.put("/api/env")
async def put_env(body: EnvUpdateBody):
    raw_updates = {k.strip(): ("" if v is None else str(v)) for k, v in (body.updates or {}).items() if k.strip()}
    if not raw_updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    # Only allowlisted keys
    unknown = [k for k in raw_updates if k not in _envm.ALLOWED_ENV]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Keys not writable via API: {', '.join(unknown)}")
    errors = _envm.validate_updates(raw_updates)
    if errors:
        raise HTTPException(status_code=400, detail={"validation": errors})
    _envm.apply_updates(raw_updates)
    masked, secrets_set, raw = _envm.masked_snapshot()
    return {"ok": True, "env": masked, "secretsSet": secrets_set}


@router.get("/api/llm/models")
@router.get("/api/openrouter/models")
async def list_llm_models(request: Request, base_url: Optional[str] = None):
    """Auto-detect available models from Ollama or any OpenAI-compatible base URL.
    Returns {models: [{id, name}], count: int, baseUrl: str, provider: str}."""
    import llm_client
    hdr_dict = dict(request.headers)
    target_url = base_url or llm_client.resolve_llm_base_url(hdr_dict)
    target_key = llm_client.resolve_llm_key(hdr_dict)

    try:
        models = llm_client.fetch_available_models(base_url=target_url, api_key=target_key)
        return {
            "models": models,
            "count": len(models),
            "baseUrl": target_url,
            "provider": "ollama" if llm_client.is_ollama(target_url) else "openai_compatible",
        }
    except Exception as e:
        return {
            "models": [],
            "count": 0,
            "baseUrl": target_url,
            "warning": str(e)[:200],
        }
