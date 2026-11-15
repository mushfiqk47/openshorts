"""Shared state for the OpenShorts server: directories, configuration
constants, the cloud-billing import gate, and the in-memory job tables.

Names that live Settings edits or tests may rebind (BILLING_ENABLED,
OUTPUT_DIR, UPLOAD_DIR, MIN_SOURCE_SECONDS, QUALITY_GATE_MIN_HEIGHT,
concurrency_semaphore) are read through this module — ``state.X`` — by every
consumer, so a monkeypatch or an os.environ write is seen at use time.
"""
import os
import re
import itertools
import asyncio
from typing import Dict, Optional

from dotenv import load_dotenv

from core.jobs import Job
from fastapi import Request

load_dotenv()

# Constants
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration
# Startup value for the job-slot semaphore. Live edits through Settings re-read
# os.environ (see _max_concurrent_jobs / _refresh_concurrency_semaphore below).
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))
_concurrency_capacity = MAX_CONCURRENT_JOBS

def _max_file_size_mb() -> int:
    """Live read of the upload size limit (Settings-writable, no restart)."""
    try:
        return max(1, int(os.environ.get("MAX_FILE_SIZE_MB", "2048")))
    except ValueError:
        return 2048

def _max_concurrent_jobs() -> int:
    """Live read of the job-slot count (Settings-writable, no restart)."""
    try:
        return max(1, int(os.environ.get("MAX_CONCURRENT_JOBS", str(MAX_CONCURRENT_JOBS))))
    except ValueError:
        return MAX_CONCURRENT_JOBS

# How TikTok receives our uploads. MEDIA_UPLOAD lands the video in the user's
# TikTok drafts so they finish the post inside TikTok's own editor; DIRECT_POST
# publishes straight to their feed, which is Upload-Post's default.
#
# Drafts are the safer default for an automated pipeline: nothing reaches an
# audience without the account owner seeing it first, and TikTok's own editor is
# where covers, sounds and hashtags actually get chosen. The UI must say so —
# a user who expects a published post and finds a draft will read it as a bug.
TIKTOK_POST_MODE = os.environ.get("TIKTOK_POST_MODE", "MEDIA_UPLOAD").strip()
# Ceiling for the working directory once it lives on a persistent volume: the
# age-based sweep alone can't stop a burst of long videos from filling the disk.
# 0 disables the cap.
OUTPUT_MAX_GB = int(os.environ.get("OUTPUT_MAX_GB", "25"))
# Same idea for source uploads, which are the biggest single files on disk.
UPLOADS_MAX_GB = int(os.environ.get("UPLOADS_MAX_GB", "15"))
# Pre-flight quality gate: warn before processing a YouTube source below this
# height (0 disables). Only applies to URLs; uploads are whatever the user gave.
QUALITY_GATE_MIN_HEIGHT = int(os.environ.get("QUALITY_GATE_MIN_HEIGHT", "720"))
# Reject sources shorter than this before starting (0 disables). A 24s YouTube
# Short cannot yield 15-60s clips: Gemini returns nothing, the job burns
# managed minutes and dies with "no usable clips" (prod 20-ago: 3 of 5 recent
# failures were exactly this, one user retrying the same 24s video).
MIN_SOURCE_SECONDS = int(os.environ.get("MIN_SOURCE_SECONDS", "45"))
QUALITY_PROBE_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quality_probe.py")
DISABLE_YOUTUBE_URL = os.environ.get("DISABLE_YOUTUBE_URL", "false").lower() in ("1", "true", "yes")
# SaaSShorts (AI UGC generator) router mount. The dashboard tabs that drove it
# were removed (2026-11-15), so it is parked: set SAASSHORTS=1 to mount
# /api/saasshorts/* plus the /gallery SEO pages again.
SAASSHORTS_ENABLED = os.environ.get("SAASSHORTS", "0").lower() in ("1", "true", "yes")

# ---- Cloud billing (paid / managed-keys) integration --------------------------
# All paid-mode code lives in the optional `cloud/` package and is imported ONLY
# when BILLING_ENABLED is set. With the flag off, the app behaves exactly as the
# self-hosted BYOK app does today (no extra dependencies required).
BILLING_ENABLED = os.environ.get("BILLING_ENABLED", "").lower() in ("1", "true", "yes")

# Job/file retention (issue #46). Self-host defaults to 24h: the 1h sweep kept
# deleting finished projects under users who never touched their env, and the
# OUTPUT_MAX_GB / UPLOADS_MAX_GB caps below already bound the disk. Cloud keeps
# the tight default because clips are archived to R2 as soon as a job finishes.
JOB_RETENTION_SECONDS = int(
    os.environ.get("JOB_RETENTION_SECONDS", "3600" if BILLING_ENABLED else "86400")
)
# Force full pipeline logs to the client even under billing (local debugging).
DEBUG_LOGS = os.environ.get("DEBUG_LOGS", "").lower() in ("1", "true", "yes")

if BILLING_ENABLED:
    import cloud
    from cloud import managed_keys, metering as _metering, config as _cloud_config, alerts as _alerts
    from cloud.auth import get_current_user_optional
else:
    cloud = None
    managed_keys = None
    _metering = None
    _cloud_config = None
    _alerts = None

    async def get_current_user_optional(request: Request):
        # No-op dependency in self-host mode: every request is anonymous / BYOK.
        return None


# Application State
# PriorityQueue holds (priority, seq, job_id). Lower priority dispatches first:
# pro=0, starter/creator=1, BYOK/anonymous/self-host=2. The seq counter keeps
# FIFO order within a priority and makes the tuples always comparable. With
# BILLING disabled every job enqueues at priority 2 → plain FIFO as before.
job_queue = asyncio.PriorityQueue()
_job_seq = itertools.count()
jobs: Dict[str, Job] = {}
thumbnail_sessions: Dict[str, Dict] = {}
publish_jobs: Dict[str, Dict] = {}  # {publish_id: {status, result, error}}
# Semester to limit concurrency to MAX_CONCURRENT_JOBS
concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

def _refresh_concurrency_semaphore() -> None:
    """Swap in a fresh semaphore when MAX_CONCURRENT_JOBS was edited via Settings.
    Slots already granted stay valid: holders release the object they acquired
    (captured at acquire time), never the module global."""
    global concurrency_semaphore, _concurrency_capacity
    desired = _max_concurrent_jobs()
    if desired != _concurrency_capacity:
        concurrency_semaphore = asyncio.Semaphore(desired)
        _concurrency_capacity = desired


def _enqueue_job(job_id: str, priority: int = 2):
    job_queue.put_nowait((priority, next(_job_seq), job_id))
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
def _safe_under(base_dir: str, user_rel_path: str) -> Optional[str]:
    """Resolve ``user_rel_path`` under ``base_dir`` and reject path traversal.

    Returns the absolute path only if it stays inside ``base_dir`` (after
    following ``..``); otherwise None. Used to sanitize client-supplied file
    references so ``../../.env`` can't escape the output directories.
    """
    base = os.path.realpath(base_dir)
    target = os.path.realpath(os.path.join(base, user_rel_path))
    if target == base or target.startswith(base + os.sep):
        return target
    return None
# Masks user:password credentials embedded in any URL (e.g. the residential
# proxy URL that yt-dlp echoes in its verbose debug output) before the line is
# ever printed to the server console or stored in the job log.
_CREDENTIAL_URL_RE = re.compile(r'(\w+://)[^:/@\s]+:[^@/\s]+@')


def _scrub_secrets(line: str) -> str:
    return _CREDENTIAL_URL_RE.sub(r'\1***:***@', line)


# Cloud users don't need (and shouldn't see) implementation details: the ingest
# plumbing (proxy / downloader / cookies) OR which AI model powers it, token
# usage and cost. These are dropped from the client view even when the line is
# emoji-prefixed. Never applied under DEBUG_LOGS (local dev sees everything).
_SENSITIVE_LOG_RE = re.compile(
    # Ingest plumbing
    r'proxy|yt[-_ ]?dlp|youtube-?dl|cookie|residential|po[_ ]?token'
    r'|player_client|extractor|\bdownload|descarg'
    # AI model / provider / cost / pipeline internals
    r'|gemini|openai|anthropic|\bflash\b|\bmodel\b|token|thinking'
    r'|\bcost\b|\$\s*[0-9]|scoring window|shortlist',
    re.IGNORECASE,
)


def _visible_logs(logs):
    """Logs to surface to the client.

    Self-host (BILLING off) shows the full pipeline output so people running
    their own instance can debug. Cloud shows a curated whitelist view
    (log_view.friendly_logs): plain progress for normal users — transcription
    percentage, clip counters — with no file paths, model names or pipeline
    internals.

    DEBUG_LOGS=true forces the full output even under billing — for local dev
    where you run in paid mode but still want the raw logs.
    """
    if not BILLING_ENABLED or DEBUG_LOGS:
        return logs
    from log_view import friendly_logs
    return friendly_logs(logs)
