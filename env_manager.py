"""Env-file sync: project follows .env, and dashboard edits persist to .env.

The dashboard previously kept API keys only in localStorage; the backend
read os.environ once at startup via load_dotenv() and never wrote back.
So changing a setting in the UI never reached the file, and editing .env
by hand required a restart to take effect.

This module makes the file the single source of truth:
  - GET /api/env reads the live file + os.environ (so manual edits are seen)
  - PUT /api/env writes through dotenv.set_key, updates os.environ in-process,
    and resets the caches that memoize env-dependent choices (NVENC probe,
    whisper singleton, etc.) so the change is live without a restart.

Only keys in ALLOWED_ENV are writable via the API — secrets like AWS keys
and billing Stripe keys stay file-only on purpose.
"""
import os
import re
from pathlib import Path
from dotenv import dotenv_values, set_key

ENV_PATH = Path(__file__).parent / ".env"

# Keys the dashboard is allowed to read/write. Masking and validation below.
ALLOWED_ENV = {
    # AI keys / models
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_REFERER",
    "OPENROUTER_TITLE",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    # Transcription (GPU-first)
    "WHISPER_MODEL",
    "WHISPER_DEVICE",
    "WHISPER_COMPUTE",
    "TRANSCRIBE_BACKEND",
    "WHISPER_FORCE_GPU",
    "ASR_GPU_CONCURRENCY",
    # Video encode / vision (GPU-first)
    "FFMPEG_ENCODER",
    "YOLO_DEVICE",
    "TRANSNETV2_DEVICE",
    # Pipeline tunables
    "CLIP_WORKERS",
    "JOB_RETENTION_SECONDS",
    "OUTPUT_MAX_GB",
    "UPLOADS_MAX_GB",
    "MAX_CONCURRENT_JOBS",
    "DISABLE_YOUTUBE_URL",
    "MAX_FILE_SIZE_MB",
}

# Validation rules for values that have a closed set
VALID_CHOICES = {
    "WHISPER_DEVICE": {"auto", "cuda", "cpu"},
    "WHISPER_COMPUTE": {"auto", "float16", "float32", "int8", "int8_float16"},
    "TRANSCRIBE_BACKEND": {"whisper", "parakeet"},
    "FFMPEG_ENCODER": {"auto", "nvenc", "x264"},
    "YOLO_DEVICE": {"auto", "cuda", "cpu"},
    "TRANSNETV2_DEVICE": {"auto", "cuda", "cpu"},
    "DISABLE_YOUTUBE_URL": {"true", "false", "1", "0", "yes", "no"},
    "WHISPER_FORCE_GPU": {"0", "1", "true", "false"},
}

# Keys whose values are secrets — returned masked on GET, never logged
SECRET_KEYS = {"OPENROUTER_API_KEY", "GEMINI_API_KEY"}

def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]

def read_env_snapshot():
    """Return {key: raw_value} for every ALLOWED key, preferring os.environ
    (live) over the file, so a just-written value is immediately visible and
    a manual file edit after startup is also picked up."""
    file_vals = {}
    if ENV_PATH.exists():
        try:
            file_vals = dotenv_values(str(ENV_PATH)) or {}
        except Exception:
            file_vals = {}
    out = {}
    for key in sorted(ALLOWED_ENV):
        # os.environ wins when set (it reflects both file-at-startup and live PUTs)
        val = os.environ.get(key)
        if val is None:
            val = file_vals.get(key, "")
        # dotenv_values may return None for present-but-empty keys
        out[key] = val if val is not None else ""
    return out

def env_file_exists() -> bool:
    return ENV_PATH.exists()

def validate_updates(updates: dict) -> dict:
    """Return {key: error} for invalid entries, empty when all ok."""
    errors = {}
    for k, v in updates.items():
        if k not in ALLOWED_ENV:
            errors[k] = "not writable via API"
            continue
        v_str = str(v).strip() if v is not None else ""
        # Choice validation
        if k in VALID_CHOICES and v_str.lower() not in VALID_CHOICES[k]:
            errors[k] = f"must be one of {sorted(VALID_CHOICES[k])}"
        # Numeric validation for a few keys
        if k in {"CLIP_WORKERS", "ASR_GPU_CONCURRENCY", "MAX_CONCURRENT_JOBS", "MAX_FILE_SIZE_MB"}:
            try:
                ival = int(v_str)
                if ival < 1 or ival > 64:
                    errors[k] = "must be 1..64"
            except ValueError:
                if v_str:
                    errors[k] = "must be an integer"
        if k in {"JOB_RETENTION_SECONDS", "OUTPUT_MAX_GB", "UPLOADS_MAX_GB"}:
            try:
                ival = int(v_str)
                if ival < 0:
                    errors[k] = "must be >= 0"
            except ValueError:
                if v_str:
                    errors[k] = "must be an integer"
    return errors

def apply_updates(updates: dict):
    """Persist to .env file and to os.environ, then reset env-dependent caches.

    Callers must have validated already. Secrets are not logged.
    """
    # Ensure file exists
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    for k, v in updates.items():
        v_str = str(v).strip() if v is not None else ""
        # Write to file (creates or updates the key in place)
        set_key(str(ENV_PATH), k, v_str)
        # Update live process env so current workers see it
        if v_str == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v_str

    # Reset caches that memoize env-derived choices — next call re-probes
    try:
        import ffmpeg_utils
        ffmpeg_utils.reset_encoder_cache()
    except Exception:
        pass
    # Whisper singleton holds device/compute in its key — force rebuild on next transcribe
    try:
        import transcribe_backends
        import threading as _th
        with transcribe_backends._whisper_lock:
            transcribe_backends._whisper_model = None
            transcribe_backends._whisper_force_cpu = False
    except Exception:
        pass

def masked_snapshot():
    """Snapshot with secrets masked and a separate flag for which are set."""
    raw = read_env_snapshot()
    masked = {}
    for k, v in raw.items():
        if k in SECRET_KEYS and v:
            masked[k] = _mask(v)
        else:
            masked[k] = v
    # Also tell the UI which secrets are actually set (so it can show "Set" vs empty)
    secrets_set = {k: bool(raw.get(k, "").strip()) for k in SECRET_KEYS}
    return masked, secrets_set, raw
