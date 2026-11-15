"""Ingest endpoints: /api/process submit, status polling, source streaming,
the download bundle, and cloud project restore / auto-restore."""
import os
import sys
import glob
import json
import shutil
import math
import time
import uuid
import asyncio
import subprocess
import zipfile
from typing import Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from server import state
from server.state import (
    jobs,
    thumbnail_sessions,
    _visible_logs,
    _max_file_size_mb,
    _enqueue_job,
    QUALITY_PROBE_SCRIPT,
    DISABLE_YOUTUBE_URL,
)
from server.billing import (
    resolve_gemini,
    gemini_missing_error,
    _resolve_ai_provider,
    _resolve_openrouter_model,
    reserve_process_minutes,
    _assert_job_owner,
)
from server.jobs import _write_resume_manifest, _locate_source

router = APIRouter()

class ProcessRequest(BaseModel):
    url: str
async def _probe_youtube_quality(url: str) -> dict:
    """Run quality_probe.py in a worker thread; {} on any failure (fail-open)."""
    def _run():
        try:
            proc = subprocess.run(
                [sys.executable, QUALITY_PROBE_SCRIPT, "--url", url],
                capture_output=True, timeout=75,
            )
            return json.loads(proc.stdout.decode(errors="replace").strip() or "{}")
        except Exception as e:
            print(f"⚠️ Quality probe failed ({e}); starting job without gate.")
            return {}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


def _media_duration_seconds(path: str) -> float:
    """Container duration via ffprobe; 0.0 on any failure (fail-open)."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, timeout=30)
        return float(proc.stdout.decode().strip() or 0)
    except Exception:
        return 0.0


def _reject_short_source(duration: float):
    raise HTTPException(status_code=400, detail=(
        f"This video is only {int(duration)}s long — clip generation needs at "
        f"least {state.MIN_SOURCE_SECONDS}s of material to cut from. It already is "
        f"short-form content."))


# Layouts the caller can let the renderer choose from, mapped to the env var
# each one is gated on. The renderer only ever picks between layouts that are
# switched on here.
#
# This is opt-in per job, not a detector running on every video, because the
# detection is not good enough to be trusted unprompted: measured over the
# 48-clip corpus, routing every video through the on-screen-content check fixed
# 13 clips and spoiled 13 others (talking heads and corner tickers demoted to a
# layout they do not need). Asking the person who knows what they uploaded costs
# them one click and removes that whole class of error. It is also what OpusClip
# does — its "applicable auto layout" panel lets the user pick which layouts the
# AI may apply.
LAYOUT_ENV = {
    "split": "SPLIT_LAYOUT",          # two speakers stacked
    "screencast": "SCREENCAST_LAYOUT",  # slides/screen share over the speaker
    "speaker_cut": "SPEAKER_CUT",     # hard cuts to whoever is talking
    "punch_in": "PUNCH_IN",           # small push on the clip's beats
}

# Stacking and cutting both need to know who is speaking.
LAYOUT_IMPLIES = {
    "split": ["SPEAKER_SIGNAL"],
    "speaker_cut": ["SPEAKER_SIGNAL"],
}


def layout_env(requested):
    """Env overrides for the layouts this job allows. Unknown names are ignored
    rather than rejected: a newer dashboard must not break an older API.

    The special value "auto" hands the choice to Gemini (one call per video).
    It composes with explicit picks: layout_picker only ever adds, so asking for
    "auto,punch_in" means "decide the layout yourself, and punch in regardless".
    """
    env = {}
    for name in requested or []:
        key = str(name).strip().lower()
        if key == "auto":
            env["AUTO_LAYOUT"] = "1"
            continue
        var = LAYOUT_ENV.get(key)
        if not var:
            continue
        env[var] = "1"
        for extra in LAYOUT_IMPLIES.get(key, []):
            env[extra] = "1"
    return env


@router.post("/api/process")
async def process_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    acknowledged: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    layouts: Optional[str] = Form(None),
    force_low_quality: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
    webhook_secret: Optional[str] = Form(None),
    target_clips: Optional[str] = Form(None),
    clip_min_seconds: Optional[str] = Form(None),
    clip_max_seconds: Optional[str] = Form(None),
    auto_hook: Optional[str] = Form(None),
    auto_hook_style: Optional[str] = Form(None),
    thumbnail_session_id: Optional[str] = Form(None)
):
    provider_kind = (os.environ.get("AI_PROVIDER") or "").strip().lower()
    api_key = await resolve_gemini(request)
    # Keyless providers (own OpenAI-compatible endpoint / local Ollama) submit
    # without an AI key; the cloud-style Gemini/OpenRouter gate only applies
    # when one of those is actually the configured brain.
    if not api_key and provider_kind not in ("custom", "ollama"):
        raise gemini_missing_error()

    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")
    force_low = str(force_low_quality).lower() in ("1", "true", "yes")

    # Handle JSON body manually for URL payload
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        url = body.get("url")
        ack_flag = bool(body.get("acknowledged"))
        force_low = bool(body.get("force_low_quality"))
        output_format = body.get("output_format")
        layouts = body.get("layouts")
        webhook_url = body.get("webhook_url")
        webhook_secret = body.get("webhook_secret")
        target_clips = body.get("target_clips")
        clip_min_seconds = body.get("clip_min_seconds")
        clip_max_seconds = body.get("clip_max_seconds")
        auto_hook = body.get("auto_hook")
        auto_hook_style = body.get("auto_hook_style")
        thumbnail_session_id = body.get("thumbnail_session_id")

    # Normalize output format (auto = keep pipeline default).
    if output_format not in ("vertical", "horizontal", "square"):
        output_format = "auto"

    # Accepts a JSON list or a comma-separated form field.
    if isinstance(layouts, str):
        layouts = [p for p in layouts.split(",") if p.strip()]
    elif not isinstance(layouts, list):
        layouts = []

    # Module handover (issue #68): reuse the Thumbnail Studio source video and
    # its transcript so publishing to YouTube can flow straight into clip
    # generation without re-uploading or re-transcribing.
    thumb_session = None
    if thumbnail_session_id and not url and not file:
        thumb_session = thumbnail_sessions.get(thumbnail_session_id)
        if not thumb_session:
            raise HTTPException(status_code=404, detail="Thumbnail session not found or expired")
        await _assert_job_owner(request, thumb_session)
        src = thumb_session.get("video_path")
        if not src or not os.path.exists(src):
            raise HTTPException(status_code=404, detail="Source video for this session is no longer on disk")

    if not url and not file and not thumb_session:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    # Completion callback: reject unsafe targets NOW (clear 400) — delivery
    # re-validates anyway, but failing at submit is the debuggable behavior.
    if webhook_url:
        from security_utils import assert_public_url, UnsafeURLError
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, assert_public_url, webhook_url)
        except UnsafeURLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid webhook_url: {e}")

    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")

    if url and DISABLE_YOUTUBE_URL:
        raise HTTPException(status_code=403, detail="YouTube URL ingest is disabled on this deployment. Please upload a file you own.")

    # Pre-flight quality gate: probe the offered resolution BEFORE starting, so
    # the user can abort (refresh cookies / update yt-dlp) instead of burning
    # 20 min on a 360p-only source. Fail-open: any probe error starts normally.
    # The probe also runs under force_low_quality so the short-source check
    # can't be bypassed through the quality-gate confirm.
    if url and (state.QUALITY_GATE_MIN_HEIGHT > 0 or state.MIN_SOURCE_SECONDS > 0):
        probe = await _probe_youtube_quality(url)
        # Hard reject, no confirm-and-retry: a too-short source fails the same
        # way on every retry, so letting the user force it just burns the job.
        source_duration = int(probe.get("duration") or 0)
        if state.MIN_SOURCE_SECONDS > 0 and 0 < source_duration < state.MIN_SOURCE_SECONDS:
            _reject_short_source(source_duration)
        max_height = int(probe.get("max_height") or 0)
        if not force_low and state.QUALITY_GATE_MIN_HEIGHT > 0 \
                and 0 < max_height < state.QUALITY_GATE_MIN_HEIGHT:
            print(f"⚠️ Quality gate: only {max_height}p available for {url} — asking user first.")
            return JSONResponse({
                "needs_confirmation": True,
                "quality_check": {
                    "max_height": max_height,
                    "min_height": state.QUALITY_GATE_MIN_HEIGHT,
                    "cookies_invalid": bool(probe.get("cookies_invalid")),
                },
            })

    # Capture attestation context for legal record (IP + timestamp + UA)
    client_ip = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        client_ip = fwd.split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")
    attestation = {
        "acknowledged": True,
        "ip": client_ip,
        "user_agent": user_agent,
        "timestamp": time.time(),
        "source": "thumbnail_session" if thumb_session else ("url" if url else "file"),
    }

    job_id = str(uuid.uuid4())
    job_output_dir = os.path.join(state.OUTPUT_DIR, job_id)
    os.makedirs(job_output_dir, exist_ok=True)

    # Prepare Command
    cmd = ["python", "-u", "main.py"] # -u for unbuffered
    env = os.environ.copy()
    # Route the key to the right provider: OpenRouter keys go to OPENROUTER_API_KEY,
    # Gemini keys to GEMINI_API_KEY. When the key looks like OpenRouter, also mirror
    # it to GEMINI_API_KEY so legacy code paths that only check that var still see a key,
    # but set OPENROUTER_API_KEY as the authoritative one.
    provider = _resolve_ai_provider(request)
    model_for_job = _resolve_openrouter_model(request) if provider == "openrouter" else ""
    if provider_kind in ("custom", "ollama"):
        # The subprocess reads AI_* / OLLAMA_* straight from the inherited env
        # (the Settings panel writes them live) - nothing to route here.
        provider = provider_kind
        print(f"[ai-provider] job={job_id} provider={provider} (env-configured)")
    elif provider == "openrouter":
        env["OPENROUTER_API_KEY"] = api_key
        env["GEMINI_API_KEY"] = api_key  # keep legacy fallback happy
        env["OPENROUTER_MODEL"] = model_for_job
        # Clear any stale Gemini model env that would shadow the OR model
        # (main.py checks OPENROUTER_MODEL first when provider is OR)
        print(f"[ai-provider] job={job_id} provider=openrouter model={model_for_job}")
    else:
        env["GEMINI_API_KEY"] = api_key
        # Ensure OpenRouter not accidentally triggered by stale env
        env.pop("OPENROUTER_API_KEY", None)
        print(f"[ai-provider] job={job_id} provider=gemini")

    # Optional layouts are per job. The renderer reads these at import time in
    # the subprocess, so they must be set before Popen — same path WATERMARK
    # already takes.
    chosen = layout_env(layouts)
    env.update(chosen)
    if chosen:
        print(f"[layouts] job={job_id} enabled={sorted(chosen)}")

    # Auto-hook: burn each clip's Gemini hook text during the render. Off when
    # the field is absent, so API/MCP/webhook callers keep their old output
    # byte-for-byte; the dashboard sends an explicit value either way.
    if str(auto_hook).lower() in ("1", "true", "yes"):
        env["AUTO_HOOK"] = "1"
        from hooks import HOOK_STYLES
        if auto_hook_style in HOOK_STYLES:
            env["AUTO_HOOK_STYLE"] = auto_hook_style
        print(f"[auto-hook] job={job_id} style={env.get('AUTO_HOOK_STYLE', 'classic')}")

    # Manual generation controls (discussion #65): optional clip-count target
    # and duration band, forwarded to the selection prompts via the same env
    # overrides the A/B harness already reads (clip_selection.py). All three
    # are honest TARGETS, not guarantees — the model may return fewer clips
    # when the material doesn't hold them. Bad values 400 instead of silently
    # producing something the user didn't ask for.
    def _gen_control(raw, name, lo, hi, integer=False):
        if raw in (None, ""):
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{name} must be a number")
        if integer and val != int(val):
            raise HTTPException(status_code=400, detail=f"{name} must be an integer")
        if not (lo <= val <= hi):
            raise HTTPException(status_code=400,
                                detail=f"{name} must be between {lo:g} and {hi:g}")
        return int(val) if integer else val

    n_clips = _gen_control(target_clips, "target_clips", 1, 15, integer=True)
    min_secs = _gen_control(clip_min_seconds, "clip_min_seconds", 5, 175)
    max_secs = _gen_control(clip_max_seconds, "clip_max_seconds", 10, 180)
    if min_secs is not None and max_secs is not None and max_secs < min_secs + 5:
        raise HTTPException(status_code=400,
                            detail="clip_max_seconds must be at least 5s above clip_min_seconds")
    if n_clips is not None:
        env["CLIP_TARGET_MIN"] = env["CLIP_TARGET_MAX"] = str(n_clips)
    if min_secs is not None:
        env["CLIP_MIN_SECONDS"] = str(min_secs)
    if max_secs is not None:
        env["CLIP_MAX_SECONDS"] = str(max_secs)
    if n_clips is not None or min_secs is not None or max_secs is not None:
        print(f"[gen-controls] job={job_id} clips={n_clips} band={min_secs}-{max_secs}")

    input_path = None
    if url:
        # Keep the downloaded source inside the job dir: the clip editor's
        # re-render path cuts new segments from it, and it ages out with the
        # rest of the job (retention window + OUTPUT_MAX_GB cap) either way.
        cmd.extend(["-u", url, "--keep-original"])
    elif thumb_session:
        # Hardlink (or copy) the session's video under the job's name so source
        # lookup, the clip editor and the preview treat it exactly like a normal
        # upload; the transcript rides along so the pipeline skips transcription.
        src = thumb_session["video_path"]
        src_duration = _media_duration_seconds(src)
        if state.MIN_SOURCE_SECONDS > 0 and 0 < src_duration < state.MIN_SOURCE_SECONDS:
            shutil.rmtree(job_output_dir, ignore_errors=True)
            _reject_short_source(src_duration)
        input_path = os.path.join(state.UPLOAD_DIR, f"{job_id}_{os.path.basename(src)}")
        try:
            os.link(src, input_path)
        except OSError:
            shutil.copyfile(src, input_path)
        cmd.extend(["-i", input_path])
        # An empty transcript (e.g. a silent or music-only source) is not worth
        # forwarding: main.py would reject it and retranscribe anyway.
        if thumb_session.get("transcript_ready") and (thumb_session.get("transcript") or {}).get("segments"):
            transcript_path = os.path.join(job_output_dir, "source_transcript.json")
            with open(transcript_path, "w") as f:
                json.dump(thumb_session["transcript"], f)
            cmd.extend(["--transcript", transcript_path])
    else:
        # Save uploaded file with size limit check.
        # basename() strips any path components from the client-supplied
        # filename so a name like "../../main.py" can't escape state.UPLOAD_DIR.
        safe_name = os.path.basename(file.filename or "upload") or "upload"
        input_path = os.path.join(state.UPLOAD_DIR, f"{job_id}_{safe_name}")

        # Read file in chunks to check size
        size = 0
        limit_bytes = _max_file_size_mb() * 1024 * 1024

        with open(input_path, "wb") as buffer:
            while content := await file.read(1024 * 1024): # Read 1MB chunks
                size += len(content)
                if size > limit_bytes:
                    os.remove(input_path)
                    shutil.rmtree(job_output_dir)
                    raise HTTPException(status_code=413, detail=f"File too large. Max size {_max_file_size_mb()}MB")
                buffer.write(content)

        upload_duration = _media_duration_seconds(input_path)
        if state.MIN_SOURCE_SECONDS > 0 and 0 < upload_duration < state.MIN_SOURCE_SECONDS:
            os.remove(input_path)
            shutil.rmtree(job_output_dir, ignore_errors=True)
            _reject_short_source(upload_duration)

        cmd.extend(["-i", input_path])

    cmd.extend(["-o", job_output_dir])
    if output_format and output_format != "auto":
        cmd.extend(["--format", output_format])

    print(f"[attestation] job={job_id} ip={attestation['ip']} source={attestation['source']} ack=true")

    # Meter + reserve minutes for managed users (no-op for BYOK / self-host).
    user_id, priority, reservation_id, user_plan = await reserve_process_minutes(request, url, input_path, job_id)
    if user_plan == "free":
        # Free-plan clips carry a burned-in watermark (applied by the main.py
        # subprocess after each clip renders).
        env["WATERMARK"] = "1"

    # Absolute-URL base for the webhook payload: explicit env wins (the API may
    # sit behind a proxy whose forwarded headers we can't trust), else what the
    # caller connected to.
    api_base = os.environ.get("PUBLIC_API_URL", "").rstrip("/") or str(request.base_url).rstrip("/")

    # Enqueue Job
    jobs[job_id] = {
        'status': 'queued',
        'logs': [f"Job {job_id} queued."],
        'cmd': cmd,
        'env': env,
        'output_dir': job_output_dir,
        'attestation': attestation,
        'user_id': user_id,
        'reservation_id': reservation_id,
        'watermark': env.get("WATERMARK") == "1",
        'webhook_url': webhook_url,
        'webhook_secret': webhook_secret,
        'base_url': api_base,
    }

    # Persist the owner so recovered jobs keep their multi-tenant guard after a
    # restart (see _recover_jobs_from_disk).
    if user_id is not None:
        try:
            os.makedirs(job_output_dir, exist_ok=True)
            with open(os.path.join(job_output_dir, ".owner"), "w") as f:
                f.write(str(user_id))
        except Exception as e:
            print(f"⚠️ Could not persist job owner for {job_id}: {e}")

    # Resume manifest: enough to re-run this job if the container dies mid-flight
    # (a redeploy). No secrets — the env is rebuilt from os.environ on resume.
    _write_resume_manifest(job_id, cmd, priority, user_id, reservation_id,
                           watermark=jobs[job_id]['watermark'],
                           webhook_url=webhook_url, webhook_secret=webhook_secret,
                           base_url=api_base)

    _enqueue_job(job_id, priority)

    return {"job_id": job_id, "status": "queued"}

@router.get("/api/status/{job_id}")
async def get_status(job_id: str, request: Request):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    await _assert_job_owner(request, job)
    return {
        "status": job['status'],
        "logs": _visible_logs(job['logs']),
        "result": job.get('result')
    }


@router.post("/api/stop/{job_id}")
async def stop_job(job_id: str, request: Request):
    """Kill a running generation (or cancel a queued one) at any moment.

    The subprocess tree dies with it: taskkill /T on Windows covers the
    ffmpeg children, killpg covers them on POSIX. The job lifecycle reports
    this as status 'stopped' - a user action, not a failure - and the wrapper
    still releases the slot and settles the minute reservation.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    await _assert_job_owner(request, job)

    if job.get("status") not in ("queued", "processing"):
        raise HTTPException(status_code=400, detail=f"Job already {job.get('status')}")

    job["stop_requested"] = True

    killed = False
    proc = job.get("process")
    if proc is not None and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
            killed = True
        else:
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                killed = True
            except (ProcessLookupError, PermissionError):
                proc.kill()
                killed = True

    job.setdefault("logs", []).append("🛑 Stop requested by user.")
    return {"ok": True, "job_id": job_id, "terminated": killed}
@router.get("/api/source/{job_id}")
async def get_source_video(job_id: str):
    """Stream a job's original source video for the live-analysis preview and
    the clip editor's source monitor.

    Uploaded sources are blob URLs in the browser and don't survive a reload,
    so the recovered session points the preview here instead. Unauthenticated
    like the /videos mount — the UUID job_id is the capability.
    """
    source_path = _locate_source(job_id)
    if not source_path:
        raise HTTPException(status_code=404, detail="Source not found")
    return FileResponse(source_path, media_type="video/mp4")


@router.get("/api/jobs/{job_id}/download-all")
async def download_all_clips(job_id: str, request: Request):
    """Bundle the current version of every clip of a job into one ZIP."""
    await _ensure_job_files(job_id, request)
    if job_id in jobs:
        await _assert_job_owner(request, jobs[job_id])

    output_dir = os.path.join(state.OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Job not found")

    with open(json_files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)

    # The metadata file on disk never carries video_url — the pipeline doesn't
    # write it, it's injected into the in-memory job record. So prefer the live
    # record (it also tracks edits like subtitled_/hook_ renames) and fall back
    # to the canonical name a job/restore rebuilds, instead of finding nothing.
    base_name = os.path.basename(json_files[0]).replace('_metadata.json', '')
    mem_clips = ((jobs.get(job_id) or {}).get('result') or {}).get('clips') or []

    files = []
    for i, clip in enumerate(data.get('shorts', [])):
        url = None
        if i < len(mem_clips):
            url = (mem_clips[i] or {}).get('video_url')
        url = url or clip.get('video_url')
        filename = (os.path.basename(url.split('/')[-1]) if url
                    else _canonical_clip_file(output_dir, base_name, i))
        path = os.path.join(output_dir, filename)
        if filename and os.path.exists(path):
            files.append((i, path))

    if not files:
        raise HTTPException(status_code=404, detail="No clip files found for this job")

    zip_path = os.path.join(output_dir, f"clips_{int(time.time())}.zip")

    def build_zip():
        # Videos are already compressed; store instead of deflate for speed.
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
            for i, path in files:
                zf.write(path, arcname=f"clip_{i + 1:02d}_{os.path.basename(path)}")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, build_zip)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"openshorts_clips_{job_id[:8]}.zip",
        background=BackgroundTask(os.remove, zip_path),
    )


# --- Project restore (paid mode) --------------------------------------------
# Re-hydrates an archived project from R2 back into output/{job_id}/ so every
# edit endpoint works on it again. Restored files land with a fresh mtime, so
# the retention clock restarts; re-restoring after a purge is cheap.
_restore_locks: Dict[str, asyncio.Lock] = {}


@router.post("/api/projects/{job_id}/restore")
async def restore_project(job_id: str, request: Request):
    if not state.BILLING_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    from sqlalchemy import select
    from cloud.auth import get_current_user_required
    from cloud.models import Project
    from cloud import database as cloud_db, storage as cloud_storage

    user = await get_current_user_required(request)
    async with cloud_db.session() as s:
        proj = (await s.execute(
            select(Project).where(Project.job_id == job_id)
        )).scalar_one_or_none()
    if proj is None or str(proj.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Per-job lock: a double click must not download the project twice.
    lock = _restore_locks.setdefault(job_id, asyncio.Lock())
    async with lock:
        job_dir = os.path.join(state.OUTPUT_DIR, job_id)

        # Idempotent fast path: everything the project needs is already on disk.
        needed = {os.path.basename(proj.metadata_r2_key)}
        for c in (proj.state or {}).get("clips", []):
            for k in ("original_file", "server_file"):
                if c.get(k):
                    needed.add(c[k])
        if os.path.isdir(job_dir) and all(
            os.path.exists(os.path.join(job_dir, f)) for f in needed
        ):
            os.utime(job_dir, None)  # restart the retention clock
        else:
            prefix = cloud_storage.job_key(user.id, job_id, "")
            keys = await asyncio.to_thread(cloud_storage.list_keys, prefix)
            if not keys:
                raise HTTPException(status_code=502,
                                    detail="Project files are no longer available")
            # Download into a temp dir first so a partial failure never leaves a
            # half-restored job dir that the fast path would mistake for complete.
            tmp_dir = job_dir + ".restoring"
            shutil.rmtree(tmp_dir, ignore_errors=True)
            os.makedirs(tmp_dir, exist_ok=True)
            sem = asyncio.Semaphore(3)

            async def _download(key):
                fname = os.path.basename(key)
                if not fname:
                    return
                async with sem:
                    await asyncio.to_thread(
                        cloud_storage.download_file, key, os.path.join(tmp_dir, fname))

            try:
                await asyncio.gather(*(_download(k) for k in keys))
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise HTTPException(status_code=502, detail=f"Restore download failed: {e}")
            # Owner sidecar keeps the multi-tenant guard after a server restart.
            with open(os.path.join(tmp_dir, ".owner"), "w") as f:
                f.write(str(user.id))
            if os.path.isdir(job_dir):
                for fname in os.listdir(tmp_dir):
                    shutil.move(os.path.join(tmp_dir, fname), os.path.join(job_dir, fname))
                shutil.rmtree(tmp_dir, ignore_errors=True)
                os.utime(job_dir, None)
            else:
                os.rename(tmp_dir, job_dir)

        # Register (or refresh) the in-memory job — same shape as
        # _recover_jobs_from_disk, so every edit endpoint works unchanged.
        json_files = glob.glob(os.path.join(job_dir, "*_metadata.json"))
        if not json_files:
            raise HTTPException(status_code=502, detail="Project metadata missing")
        with open(json_files[0], 'r') as f:
            data = json.load(f)
        base_name = os.path.basename(json_files[0]).replace('_metadata.json', '')
        clips = data.get('shorts', [])
        for i, clip in enumerate(clips):
            if not clip.get('video_url'):
                clip['video_url'] = (
                    f"/videos/{job_id}/"
                    f"{_canonical_clip_file(job_dir, base_name, i)}")
        jobs[job_id] = {
            'status': 'completed',
            'logs': ["♻️ Project restored from your library."],
            'output_dir': job_dir,
            'user_id': str(user.id),
            'result': {'clips': clips, 'cost_analysis': data.get('cost_analysis')},
        }

    return {
        "job_id": job_id,
        "status": "completed",
        "result": jobs[job_id]['result'],
        "project_state": proj.state,
        "title": proj.title,
    }


async def _ensure_job_files(job_id: str, request: Request) -> bool:
    """Make a completed job usable again after its working files vanished.

    state.OUTPUT_DIR is not durable — a container restart or redeploy wipes it — so
    endpoints that read a job's files would 404 on a project the user can still
    see in their library. Pull it back from R2 on demand (same path as the
    explicit /restore), so editing keeps working instead of dead-ending.

    Returns True when the job is available afterwards. Never raises: callers
    keep their own 404s for jobs that genuinely don't exist.
    """
    job_dir = os.path.join(state.OUTPUT_DIR, job_id)
    if job_id in jobs and glob.glob(os.path.join(job_dir, "*_metadata.json")):
        return True
    if not state.BILLING_ENABLED:
        return False
    try:
        await restore_project(job_id, request)
        print(f"♻️  Auto-restored {job_id} from the library (working files were gone).")
        return True
    except HTTPException:
        return False
    except Exception as e:
        print(f"⚠️  Auto-restore failed for {job_id}: {e}")
        return False
