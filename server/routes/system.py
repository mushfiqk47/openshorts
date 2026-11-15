"""System surface: health, config, env-file sync, transcription model
management (nemo-speech runtime), AI-provider smoke test, and the OpenRouter
free-model cache."""
import os
import json
import time
import asyncio
import threading
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import env_manager as _envm
from server import state
from server.state import (
    cloud,
    JOB_RETENTION_SECONDS,
    DISABLE_YOUTUBE_URL,
)

router = APIRouter()

@router.get("/health")
async def health():
    """Lightweight liveness probe for uptime monitoring / Coolify health checks."""
    return {"status": "ok"}

@router.get("/api/config")
async def get_config():
    return {
        "youtubeUrlEnabled": not DISABLE_YOUTUBE_URL,
        "billingEnabled": state.BILLING_ENABLED,
        "googleAuthEnabled": bool(state.BILLING_ENABLED and cloud.settings.google_auth_enabled),
        "jobRetentionSeconds": JOB_RETENTION_SECONDS,
        "openRouterEnabled": True,
        "defaultOpenRouterModel": os.environ.get("OPENROUTER_MODEL", "openrouter/free"),
    }


# ---- Env-file sync (project follows .env, dashboard writes it) --------------
import env_manager as _envm


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


class AITestBody(BaseModel):
    # Draft values from the settings form, so the button tests what the user
    # typed before it is saved. Keys must be in ALLOWED_ENV; anything missing
    # falls back to the live .env values.
    updates: Dict[str, str] = {}


# ---- Transcription models (nemo-speech runtime) -----------------------------
# The dashboard's transcription card drives these: list what the runtime
# offers, download a model, and smoke-test the whole GPU chain.
_asr_job_state = {"running": False, "kind": None, "model": None,
                  "ok": None, "detail": "", "started": None}
_asr_job_lock = threading.Lock()


def _asr_list_models():
    """ASR models the runtime offers + whether each is already downloaded."""
    from transcribe_backends import _resolve_nemo_bin, _nemo_cache_root
    proc = subprocess.run(
        [_resolve_nemo_bin(), "model", "list", "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "model list failed").strip()[-300:])
    data = json.loads(proc.stdout)
    cache_root = _nemo_cache_root()
    out = []
    for m in data.get("models", []):
        if "asr" not in (m.get("roles") or []):
            continue
        rev_dir = cache_root / str(m.get("repo")) / str(m.get("revision") or "")
        out.append({
            "alias": (m.get("aliases") or [m.get("repo")])[0],
            "aliases": m.get("aliases") or [],
            "repo": m.get("repo"),
            "license_url": m.get("license_url"),
            "cached": rev_dir.is_dir(),
        })
    return out


def _asr_run_job(kind, model):
    """Background worker for download / smoke-test — one at a time."""
    from transcribe_backends import ensure_model_cached, smoke_test_transcription
    try:
        if kind == "download":
            ok, detail = ensure_model_cached(model)
            _asr_job_state["detail"] = detail
        else:
            ok, info = smoke_test_transcription()
            _asr_job_state["detail"] = info if isinstance(info, str) else json.dumps(info)
        _asr_job_state["ok"] = bool(ok)
    except Exception as e:
        _asr_job_state["ok"] = False
        _asr_job_state["detail"] = str(e)
    finally:
        _asr_job_state["running"] = False
        _asr_job_state["finished"] = datetime.now(timezone.utc).isoformat()


class ASRActionBody(BaseModel):
    model: Optional[str] = None


@router.get("/api/asr/models")
async def get_asr_models():
    from transcribe_backends import DEFAULT_NEMO_MODEL
    try:
        models = _asr_list_models()
        active = (os.environ.get("NEMO_ASR_MODEL") or "").strip() or DEFAULT_NEMO_MODEL
        return {"ok": True, "models": models, "active": active,
                "job": {k: v for k, v in _asr_job_state.items() if k != "kind"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/asr/download")
async def download_asr_model(body: ASRActionBody):
    """Download (pull) an ASR model. Single-flight: one job at a time."""
    from transcribe_backends import DEFAULT_NEMO_MODEL
    model = (body.model or "").strip() or (os.environ.get("NEMO_ASR_MODEL") or "").strip() or DEFAULT_NEMO_MODEL
    with _asr_job_lock:
        if _asr_job_state["running"]:
            raise HTTPException(status_code=409, detail="A transcription job (download or test) is already running")
        _asr_job_state.update(running=True, kind="download", model=model,
                              ok=None, detail="", started=datetime.now(timezone.utc).isoformat(),
                              finished=None)
    threading.Thread(target=_asr_run_job, args=("download", model), daemon=True).start()
    return {"ok": True, "model": model}


@router.post("/api/asr/smoke-test")
async def smoke_test_asr():
    """Run the full GPU transcription chain against a generated test tone."""
    with _asr_job_lock:
        if _asr_job_state["running"]:
            raise HTTPException(status_code=409, detail="A transcription job (download or test) is already running")
        _asr_job_state.update(running=True, kind="smoke-test", model=None,
                              ok=None, detail="", started=datetime.now(timezone.utc).isoformat(),
                              finished=None)
    threading.Thread(target=_asr_run_job, args=("smoke-test", None), daemon=True).start()
    return {"ok": True}


@router.get("/api/asr/status")
async def get_asr_job_status():
    return {k: v for k, v in _asr_job_state.items() if k != "kind"}


@router.post("/api/ai/test")
async def test_ai_connection(body: AITestBody):
    """Ping the configured AI provider with a tiny completion.

    Tests exactly what the clip pipeline would use: AI_PROVIDER picks the
    backend ('auto' = OpenRouter when its key is set, else Gemini), and draft
    values from the settings form override the saved .env so credentials can
    be verified before they are persisted. Returns
    {ok, provider, model, latencyMs, detail | error}."""
    draft = {k.strip(): str(v).strip() for k, v in (body.updates or {}).items()
             if k.strip() in _envm.ALLOWED_ENV and v is not None and str(v).strip()}

    def cfg(key: str) -> str:
        return draft.get(key) or (os.environ.get(key) or "").strip()

    provider = (cfg("AI_PROVIDER") or "auto").lower()

    def ping(base_url: str, api_key: str, model: str):
        from openai import OpenAI
        client = OpenAI(api_key=api_key or "no-key", base_url=base_url, timeout=45.0)
        t0 = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            # No temperature (some reasoning endpoints reject 0) and a token
            # ceiling high enough that reasoning models still emit text.
            max_tokens=512,
        )
        ms = int((time.time() - t0) * 1000)
        text = ""
        if resp.choices:
            text = (resp.choices[0].message.content or "").strip()
        return {"ok": True, "provider": provider, "model": model,
                "latencyMs": ms, "detail": text[:120] or "(empty reply)"}

    try:
        if provider == "custom":
            base = cfg("AI_BASE_URL")
            if not base:
                return {"ok": False, "provider": provider, "error": "AI_BASE_URL is not set"}
            if not cfg("AI_MODEL"):
                return {"ok": False, "provider": provider, "error": "AI_MODEL is not set"}
            return ping(base, cfg("AI_API_KEY"), cfg("AI_MODEL"))
        if provider == "ollama":
            base = (cfg("OLLAMA_URL") or "http://localhost:11434").rstrip("/") + "/v1"
            return ping(base, "ollama", cfg("OLLAMA_MODEL") or "lfm3-vl:2b-q4_K_M")
        if provider in ("openrouter", "auto"):
            key = cfg("OPENROUTER_API_KEY")
            if key:
                from openrouter_client import OPENROUTER_BASE
                return ping(OPENROUTER_BASE, key, cfg("OPENROUTER_MODEL") or "openrouter/free")
            if provider == "openrouter":
                return {"ok": False, "provider": provider, "error": "OPENROUTER_API_KEY is not set"}
            # auto falls through to Gemini when no OpenRouter key is set
        if provider in ("gemini", "auto"):
            key = cfg("GEMINI_API_KEY")
            if not key:
                return {"ok": False, "provider": provider,
                        "error": "no key configured (set OPENROUTER_API_KEY or GEMINI_API_KEY)"}
            return ping("https://generativelanguage.googleapis.com/v1beta/openai/",
                        key, cfg("GEMINI_MODEL") or "gemini-2.5-flash-lite")
        return {"ok": False, "provider": provider, "error": f"unknown AI_PROVIDER '{provider}'"}
    except Exception as e:
        return {"ok": False, "provider": provider,
                "error": f"{type(e).__name__}: {e}"[:400]}


# Cache for OpenRouter free models (1 hour). Avoids hammering the API on every settings open.
_OR_MODELS_CACHE = {"time": 0, "data": []}


@router.get("/api/openrouter/models")
async def list_openrouter_models(request: Request):
    """Auto-detect free models from OpenRouter. Uses the caller's key if provided,
    otherwise the server's env key, otherwise tries unauthenticated (public list is often allowed).
    Returns {models: [{id, name, pricing}], cached: bool}."""
    import httpx as _httpx

    # Prefer caller's key (header) so free-detection works even before env is set
    api_key = None
    for hdr in ("X-OpenRouter-Key", "X-OpenRouter-API-Key", "X-Gemini-Key"):
        v = request.headers.get(hdr)
        if v and v.strip().startswith("sk-or-"):
            api_key = v.strip()
            break
    if not api_key:
        api_key = (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY") or "").strip() or None

    # Serve from cache if fresh (60 min)
    now = time.time()
    if _OR_MODELS_CACHE["data"] and now - _OR_MODELS_CACHE["time"] < 3600:
        return {"models": _OR_MODELS_CACHE["data"], "cached": True, "count": len(_OR_MODELS_CACHE["data"])}

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    # OpenRouter recommends these but not required for models list
    headers["HTTP-Referer"] = os.environ.get("OPENROUTER_REFERER", "http://localhost:5175")
    headers["X-Title"] = os.environ.get("OPENROUTER_TITLE", "OpenShorts")

    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            # 401 on free list often still returns data; if 401 fallback to unauthenticated try
            if resp.status_code == 401 and api_key:
                async with _httpx.AsyncClient(timeout=15) as c2:
                    resp = await c2.get("https://openrouter.ai/api/v1/models", headers={
                        "HTTP-Referer": headers["HTTP-Referer"], "X-Title": headers["X-Title"]
                    })
            resp.raise_for_status()
            data = resp.json()
            all_models = data.get("data", []) if isinstance(data, dict) else []
            free = []
            for m in all_models:
                mid = m.get("id") or ""
                pricing = m.get("pricing") or {}
                # Free = :free suffix OR prompt+completion == 0
                is_free = mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")
                if is_free:
                    free.append({
                        "id": mid,
                        "name": m.get("name") or mid,
                        "pricing": pricing,
                        "context_length": m.get("context_length"),
                    })
            # Sort: :free first, then by name
            free.sort(key=lambda x: (0 if x["id"].endswith(":free") else 1, x["id"]))
            # Cache
            _OR_MODELS_CACHE["time"] = now
            _OR_MODELS_CACHE["data"] = free
            return {"models": free, "cached": False, "count": len(free)}
    except Exception as e:
        # On error, return cached if any, else empty with error
        if _OR_MODELS_CACHE["data"]:
            return {"models": _OR_MODELS_CACHE["data"], "cached": True, "count": len(_OR_MODELS_CACHE["data"]), "warning": str(e)[:200]}
        raise HTTPException(status_code=502, detail=f"Could not fetch OpenRouter models: {e}")
