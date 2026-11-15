"""The job engine: queue worker, subprocess runner, artifact surgery,
disk caps, recovery/resume, webhook delivery, and the settlement chain that
runs when a job reaches a terminal state."""
import os
import re
import glob
import json
import shutil
import math
import time
import subprocess
import threading
import asyncio
from datetime import datetime, timezone

import httpx
import recut
from s3_uploader import upload_job_artifacts

from server import state
from core.artifacts import (  # noqa: E402
    canonical_clip_file as _canonical_clip_file,
    strip_burned_captions as _strip_burned_captions,
    strip_burned_hook as _strip_burned_hook,
    clip_window,
    load_metadata,
    metadata_base_name,
)
from server.state import (
    job_queue,
    jobs,
    THUMBNAILS_DIR,
    JOB_RETENTION_SECONDS,
    UPLOADS_MAX_GB,
    OUTPUT_MAX_GB,
    MAX_CONCURRENT_JOBS,
    _refresh_concurrency_semaphore,
    managed_keys,
    cloud,
    _metering,
    _cloud_config,
    _alerts,
    _enqueue_job,
    _scrub_secrets,
)

def _relocate_root_job_artifacts(job_id: str, job_output_dir: str) -> bool:
    """
    Backward-compat rescue:
    If main.py accidentally wrote metadata/clips into state.OUTPUT_DIR root (e.g. output/<jobid>_...),
    move them into output/<job_id>/ so the API can find and serve them.
    """
    try:
        os.makedirs(job_output_dir, exist_ok=True)
        root = state.OUTPUT_DIR
        pattern = os.path.join(root, f"{job_id}_*_metadata.json")
        meta_candidates = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
        if not meta_candidates:
            return False

        # Move the newest metadata and its associated clips.
        metadata_path = meta_candidates[0]
        base_name = metadata_base_name(metadata_path)

        # Move metadata
        dest_metadata = os.path.join(job_output_dir, os.path.basename(metadata_path))
        if os.path.abspath(metadata_path) != os.path.abspath(dest_metadata):
            shutil.move(metadata_path, dest_metadata)

        # Move any clips that match the same base_name into the job folder
        clip_pattern = os.path.join(root, f"{base_name}_clip_*.mp4")
        for clip_path in glob.glob(clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        # Also move any temp_ clips that might remain
        temp_clip_pattern = os.path.join(root, f"temp_{base_name}_clip_*.mp4")
        for clip_path in glob.glob(temp_clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        return True
    except Exception:
        return False

def _reapply_captions(job_id, clip_index, video_path):
    """Re-burn the default captions onto a freshly derived file.

    Captions must always be the LAST layer. Editing or hooking a clip that
    already had them burned in produced `edited_subtitled_<...>`, and the next
    subtitle pass then stacked a second caption layer on top of the first —
    visibly doubled and unreadable in real user clips (26-jul-2026). So the
    derivation runs on the clean file and captions go back on afterwards.

    Returns the captioned path, or None if there was nothing to caption.
    """
    try:
        meta_files = glob.glob(os.path.join(state.OUTPUT_DIR, job_id, "*_metadata.json"))
        if not meta_files:
            return None
        data = load_metadata(meta_files[0])
        transcript = data.get('transcript')
        clips = data.get('shorts', [])
        if not transcript or clip_index >= len(clips):
            return None
        clip = clips[clip_index]
        import main as _main
        # A recut clip is a concatenation of source segments: clip_window
        # remaps the transcript clip-relative (same trick /api/subtitle uses).
        w_transcript, w_start, w_end = clip_window(transcript, clip)
        return _main.auto_caption_clip(video_path, w_transcript, w_start, w_end)
    except Exception as e:
        print(f"⚠️  Could not re-apply captions to {video_path}: {e}")
        return None


def _recover_jobs_from_disk():
    """Rebuild completed jobs from state.OUTPUT_DIR after a restart (issue #46 / #18).

    Jobs live in memory, so a restart used to orphan finished clips that are
    still on disk: the frontend restores the job_id from localStorage but every
    endpoint answers 404 "Job not found". Rebuild a minimal completed record
    for each job directory that has a metadata JSON.
    """
    recovered = 0
    try:
        entries = os.listdir(state.OUTPUT_DIR)
    except FileNotFoundError:
        return
    for job_id in entries:
        job_path = os.path.join(state.OUTPUT_DIR, job_id)
        if not os.path.isdir(job_path) or job_id in jobs:
            continue
        json_files = glob.glob(os.path.join(job_path, "*_metadata.json"))
        if not json_files:
            continue
        try:
            data = load_metadata(json_files[0])
            base_name = metadata_base_name(json_files[0])
            clips = data.get('shorts', [])
            for i, clip in enumerate(clips):
                if not clip.get('video_url'):
                    clip['video_url'] = (
                        f"/videos/{job_id}/"
                        f"{_canonical_clip_file(job_path, base_name, i)}")
            owner = None
            owner_path = os.path.join(job_path, ".owner")
            if os.path.exists(owner_path):
                with open(owner_path) as f:
                    raw = f.read().strip()
                owner = int(raw) if raw.isdigit() else (raw or None)
            jobs[job_id] = {
                'status': 'completed',
                'logs': ["♻️ Job recovered from disk after server restart."],
                'output_dir': job_path,
                'user_id': owner,
                'result': {'clips': clips, 'cost_analysis': data.get('cost_analysis')},
            }
            recovered += 1
        except Exception as e:
            print(f"⚠️ Could not recover job {job_id}: {e}")
    if recovered:
        print(f"♻️  Recovered {recovered} completed job(s) from disk.")


# --- Mid-flight job resume (survive a redeploy without losing work) ----------
# A job lives only in memory, so killing the container mid-processing used to
# lose it: the user's clip just stops. We persist a tiny manifest per job and,
# on startup, re-enqueue any that were interrupted — the user sees it resume
# instead of vanish. Bounded by MAX_RESUME_ATTEMPTS so a video that reliably
# crashes the worker can't crashloop the service.
_RESUME_FILE = ".resume.json"
MAX_RESUME_ATTEMPTS = 2


def _write_resume_manifest(job_id, cmd, priority, user_id, reservation_id, watermark,
                           webhook_url=None, webhook_secret=None, base_url=None):
    try:
        path = os.path.join(state.OUTPUT_DIR, job_id, _RESUME_FILE)
        with open(path, "w") as f:
            json.dump({
                "cmd": cmd, "priority": priority,
                "user_id": None if user_id is None else str(user_id),
                "reservation_id": reservation_id,
                "watermark": bool(watermark), "attempts": 0,
                # The caller's webhook must survive a redeploy: a pipeline that
                # relies on the callback would otherwise hang forever on a job
                # that resumed fine. The secret is the caller's own HMAC value,
                # stored next to their video on the same disk — not a server
                # credential (those are rebuilt from os.environ on resume).
                "webhook_url": webhook_url,
                "webhook_secret": webhook_secret,
                "base_url": base_url,
            }, f)
    except Exception as e:
        print(f"⚠️ Could not write resume manifest for {job_id}: {e}")


def _clear_resume_manifest(job_id):
    """Drop the manifest once a job reaches a terminal state, so it is never
    re-run on a later restart. Only an interrupted (still-running) job keeps it."""
    try:
        os.remove(os.path.join(state.OUTPUT_DIR, job_id, _RESUME_FILE))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️ Could not clear resume manifest for {job_id}: {e}")


def _resume_interrupted_jobs() -> set:
    """Re-enqueue jobs that were mid-processing when the server last stopped.

    Runs after _recover_jobs_from_disk: a job whose clips already finished has a
    metadata JSON and is recovered as 'completed', so we only resume manifests
    with no metadata yet (analysis never finished).

    Returns the set of reservation ids for the resumed jobs, so the caller can
    keep them out of the orphaned-reservation refund. Does NO DB work — the DB
    engine isn't up yet at this point in startup. A poison job (too many
    attempts) is simply not resumed; its reservation is then refunded as a
    normal orphan.
    """
    keep_reservations: set = set()
    try:
        entries = os.listdir(state.OUTPUT_DIR)
    except FileNotFoundError:
        return keep_reservations
    resumed = 0
    for job_id in entries:
        job_path = os.path.join(state.OUTPUT_DIR, job_id)
        manifest_path = os.path.join(job_path, _RESUME_FILE)
        if not os.path.isfile(manifest_path):
            continue
        # Already finished generating clips → recovered as completed elsewhere.
        if glob.glob(os.path.join(job_path, "*_metadata.json")):
            _clear_resume_manifest(job_id)
            continue
        try:
            with open(manifest_path) as f:
                m = json.load(f)
        except Exception as e:
            print(f"⚠️ Bad resume manifest for {job_id}: {e}")
            continue

        attempts = int(m.get("attempts", 0)) + 1
        user_id = m.get("user_id")
        reservation_id = m.get("reservation_id")
        if attempts > MAX_RESUME_ATTEMPTS:
            # Poison job: don't resume. Leaving its reservation out of the keep
            # set lets the orphan sweep refund it, and the user can retry by hand.
            print(f"🛑 Job {job_id} exceeded {MAX_RESUME_ATTEMPTS} resume attempts — giving up.")
            _clear_resume_manifest(job_id)
            continue

        # Rebuild env from scratch — the manifest holds no secrets. Managed
        # (cloud) jobs get the server key; self-host falls back to its env key.
        env = os.environ.copy()
        if state.BILLING_ENABLED and user_id is not None:
            try:
                env["GEMINI_API_KEY"] = managed_keys.gemini_key()
            except Exception:
                pass
        if m.get("watermark"):
            env["WATERMARK"] = "1"
        else:
            env.pop("WATERMARK", None)

        m["attempts"] = attempts
        try:
            with open(manifest_path, "w") as f:
                json.dump(m, f)
        except Exception:
            pass

        jobs[job_id] = {
            'status': 'queued',
            'logs': [f"♻️ Resuming your video after a server update (attempt {attempts})."],
            'cmd': m.get("cmd"),
            'env': env,
            'output_dir': job_path,
            'user_id': None if user_id is None else user_id,
            'reservation_id': reservation_id,
            'watermark': bool(m.get("watermark")),
            'webhook_url': m.get("webhook_url"),
            'webhook_secret': m.get("webhook_secret"),
            'base_url': m.get("base_url"),
        }
        if reservation_id:
            keep_reservations.add(str(reservation_id))
        _enqueue_job(job_id, int(m.get("priority", 2)))
        resumed += 1
    if resumed:
        print(f"♻️  Re-enqueued {resumed} interrupted job(s) after restart.")
    return keep_reservations


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _enforce_uploads_size_cap():
    """Delete the oldest source uploads while state.UPLOAD_DIR is over UPLOADS_MAX_GB.

    Sources are only needed while a job runs (and for the preview afterwards),
    but they're the biggest files on disk — up to MAX_FILE_SIZE_MB each.
    """
    cap = UPLOADS_MAX_GB * 1024 ** 3
    if cap <= 0:
        return
    used = _dir_size(state.UPLOAD_DIR)
    if used <= cap:
        return
    files = []
    for name in os.listdir(state.UPLOAD_DIR):
        p = os.path.join(state.UPLOAD_DIR, name)
        if os.path.isfile(p):
            try:
                files.append((os.path.getmtime(p), p, os.path.getsize(p)))
            except OSError:
                pass
    files.sort()
    print(f"🧹 Uploads at {used / 1024**3:.1f} GB (cap {UPLOADS_MAX_GB} GB) — trimming.")
    for _mtime, path, size in files:
        if used <= cap:
            break
        try:
            os.remove(path)
            used -= size
            print(f"🧹 Size cap: removed upload {os.path.basename(path)}")
        except OSError:
            pass


def _enforce_output_size_cap():
    """Delete the oldest job dirs while state.OUTPUT_DIR is over OUTPUT_MAX_GB."""
    cap = OUTPUT_MAX_GB * 1024 ** 3
    if cap <= 0:
        return
    used = _dir_size(state.OUTPUT_DIR)
    if used <= cap:
        return
    thumbs = os.path.basename(THUMBNAILS_DIR)
    candidates = []
    for job_id in os.listdir(state.OUTPUT_DIR):
        if job_id == thumbs:
            continue
        p = os.path.join(state.OUTPUT_DIR, job_id)
        if os.path.isdir(p):
            try:
                candidates.append((os.path.getmtime(p), p, job_id))
            except OSError:
                pass
    candidates.sort()  # oldest first
    print(f"🧹 Output dir at {used / 1024**3:.1f} GB (cap {OUTPUT_MAX_GB} GB) — trimming.")
    for _mtime, path, job_id in candidates:
        if used <= cap:
            break
        size = _dir_size(path)
        shutil.rmtree(path, ignore_errors=True)
        jobs.pop(job_id, None)
        used -= size
        print(f"🧹 Size cap: purged {job_id} ({size / 1024**2:.0f} MB)")


async def cleanup_jobs():
    """Background task to remove old jobs and files."""
    import time
    print("🧹 Cleanup task started.")
    while True:
        try:
            await asyncio.sleep(300) # Check every 5 minutes
            now = time.time()
            
            # Simple directory cleanup based on modification time
            # Check state.OUTPUT_DIR
            for job_id in os.listdir(state.OUTPUT_DIR):
                # Not a job: the thumbnails dir backs a StaticFiles mount, so
                # deleting it would 500 every /thumbnails request until reboot.
                if job_id == os.path.basename(THUMBNAILS_DIR):
                    continue
                job_path = os.path.join(state.OUTPUT_DIR, job_id)
                if os.path.isdir(job_path):
                    if now - os.path.getmtime(job_path) > JOB_RETENTION_SECONDS:
                        print(f"🧹 Purging old job: {job_id}")
                        shutil.rmtree(job_path, ignore_errors=True)
                        if job_id in jobs:
                            del jobs[job_id]

            # Hard disk cap. The time-based sweep above bounds the *age* of what
            # we keep, not its size: a burst of long videos can fill the volume
            # inside one retention window. Drop the oldest jobs until we're back
            # under the cap — clips are already archived to R2 and get restored
            # on demand, so this only costs a re-download.
            _enforce_output_size_cap()
            _enforce_uploads_size_cap()

            # Cleanup SaaSShorts jobs from memory — they only exist when the
            # optional SAASSHORTS router is mounted.
            if state.SAASSHORTS_ENABLED:
                from server.routes.saasshorts import saas_jobs

                saas_expired = [
                    jid for jid, jdata in list(saas_jobs.items())
                    if jdata.get("status") in ("completed", "failed")
                    and jdata.get("output_dir")
                    and os.path.isdir(jdata["output_dir"])
                    and now - os.path.getmtime(jdata["output_dir"]) > JOB_RETENTION_SECONDS
                ]
                for jid in saas_expired:
                    del saas_jobs[jid]

            # Cleanup Uploads
            for filename in os.listdir(state.UPLOAD_DIR):
                file_path = os.path.join(state.UPLOAD_DIR, filename)
                try:
                    if now - os.path.getmtime(file_path) > JOB_RETENTION_SECONDS:
                         os.remove(file_path)
                except Exception: pass

        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

async def process_queue():
    """Background worker to process jobs from the queue with concurrency limit."""
    print(f"🚀 Job Queue Worker started with {MAX_CONCURRENT_JOBS} concurrent slots.")
    while True:
        try:
            # Wait for a job (priority, seq, job_id) — lowest priority first.
            _priority, _seq, job_id = await job_queue.get()

            # Live Settings edits resize the slot count between dispatches.
            _refresh_concurrency_semaphore()
            sem = state.concurrency_semaphore

            # Acquire semaphore slot (waits if max jobs are running)
            await sem.acquire()
            print(f"🔄 Acquired slot for job: {job_id}")

            # Process in background task to not block the loop (allowing other slots to fill)
            asyncio.create_task(run_job_wrapper(job_id, sem))
            
        except Exception as e:
            print(f"❌ Queue dispatch error: {e}")
            await asyncio.sleep(1)

# Monthly proxy bandwidth counter (in-memory; an alert threshold, not a bill —
# losing it on a deploy just means the alert re-arms from 0 mid-month).
_proxy_month = {"month": None, "bytes": 0, "alerted": False}
PROXY_ALERT_GB = 100


async def _track_proxy_usage(job_id):
    nbytes = (jobs.get(job_id) or {}).get('proxy_bytes') or 0
    if not nbytes:
        return
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if _proxy_month["month"] != month:
        _proxy_month.update(month=month, bytes=0, alerted=False)
    _proxy_month["bytes"] += nbytes
    gb = _proxy_month["bytes"] / 1e9
    if gb >= PROXY_ALERT_GB and not _proxy_month["alerted"] and _alerts:
        _proxy_month["alerted"] = True
        try:
            await _alerts.send_admin_alert(
                "Proxy bandwidth threshold",
                f"Managed downloads have used {gb:.1f} GB of proxy bandwidth in {month} "
                f"(threshold {PROXY_ALERT_GB} GB). Review free-plan usage.",
            )
        except Exception as e:
            print(f"⚠️ Proxy alert failed: {e}")


async def run_job_wrapper(job_id, sem=None):
    """Wrapper to run job and release the semaphore slot it was granted"""
    if sem is None:
        sem = state.concurrency_semaphore
    try:
        job = jobs.get(job_id)
        if job:
            await run_job(job_id, job)
    except Exception as e:
         print(f"❌ Job wrapper error {job_id}: {e}")
    finally:
        # The subprocess returned (success or genuine failure) — a terminal
        # state, so drop the resume manifest. It only survives if the container
        # was killed mid-run, which is exactly when we want to resume.
        _clear_resume_manifest(job_id)
        # Settle the minute reservation (managed jobs only): commit on success,
        # release otherwise so the minutes go back to the user.
        await _settle_reservation(job_id)
        # Archive the completed clips to the user's durable R2 library (history).
        await _archive_managed_job(job_id)
        # Fire the caller's webhook (after archive, so durable links exist).
        await _notify_job_webhook(job_id)
        # Operational alerting for managed jobs (proxy out of credits / failures).
        await _record_job_alert(job_id)
        # Accumulate proxy bandwidth for the monthly cost alert.
        await _track_proxy_usage(job_id)
        # Tell the owner their clips are ready (managed jobs, once per job).
        await _notify_clips_ready(job_id)
        # Telegram pulse for high-signal activity (first clip / paid user).
        await _notify_clip_activity(job_id)
        # Always release semaphore and mark queue task done
        sem.release()
        job_queue.task_done()
        print(f"✅ Released slot for job: {job_id}")


async def _archive_managed_job(job_id):
    if not state.BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get('user_id') or job.get('status') != 'completed':
        return
    clips = (job.get('result') or {}).get('clips') or []
    if not clips:
        return
    try:
        await cloud.videos.archive_job(job['user_id'], job_id, clips, job['output_dir'])
    except Exception as e:
        print(f"⚠️  R2 archive error for {job_id}: {e}")


def _archive_clip_edit_bg(job_id: str, clip_index: int, filename: str):
    """Fire-and-forget R2 re-archive of an edited clip (managed jobs only).

    Keeps the user's durable library (history/projects) pointing at the current
    version of each clip without blocking the edit response."""
    if not state.BILLING_ENABLED:
        return
    user_id = (jobs.get(job_id) or {}).get('user_id')
    if not user_id:
        return
    output_dir = os.path.join(state.OUTPUT_DIR, job_id)

    async def _run():
        try:
            await cloud.videos.archive_clip_edit(user_id, job_id, clip_index, output_dir, filename)
        except Exception as e:
            print(f"⚠️  R2 edit archive error for {job_id}: {e}")

    asyncio.create_task(_run())


async def _notify_clips_ready(job_id):
    """Email the owner when their clips finish — processing takes minutes, so
    this lets them close the tab. Once per job (email_sent flag)."""
    if not state.BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get('user_id') or job.get('status') != 'completed' or job.get('email_sent'):
        return
    clips = (job.get('result') or {}).get('clips') or []
    if not clips:
        return
    job['email_sent'] = True
    try:
        from cloud.database import session as cloud_session
        from cloud.models import User
        from cloud.emails import send_clips_ready_email
        async with cloud_session() as s:
            user = await s.get(User, job['user_id'])
        if not user or not user.email:
            return
        title = clips[0].get('video_title_for_youtube_short') or clips[0].get('title') or "Your video"
        # #app opens the app itself. The bare frontend URL showed the marketing
        # landing to anyone whose browser had not already set the skip flag,
        # which is the wrong page for someone clicking "View my clips".
        await send_clips_ready_email(user.email, title, len(clips),
                                     f"{_cloud_config.settings.frontend_url}/#app")
    except Exception as e:
        print(f"⚠️  Clips-ready email error for {job_id}: {e}")


async def _notify_clip_activity(job_id):
    """Telegram pulse when a PAID user's clips are created. Free-tier activity
    (including first clips) is deliberately silent: at current signup volume it
    drowned the ops channel without being actionable.
    Telegram-only (best effort, no email)."""
    if not state.BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get('user_id') or job.get('status') != 'completed':
        return
    clips = (job.get('result') or {}).get('clips') or []
    if not clips:
        return
    try:
        from cloud.database import session as cloud_session
        from cloud.models import User
        from cloud import metering
        async with cloud_session() as s:
            user = await s.get(User, job['user_id'])
            if not user:
                return
            sub = await metering._active_subscription(s, user.id)
        if sub is None:
            return
        title = clips[0].get('video_title_for_youtube_short') or clips[0].get('title') or "video"
        n = len(clips)
        await _alerts.send_telegram(
            f"🎬 Clips created\n{user.email} ({sub.plan}) — “{title}” ({n} clip{'s' if n != 1 else ''})")
    except Exception as e:
        print(f"⚠️  Clip-activity notify error for {job_id}: {e}")


# Markers that identify a line as an actual error rather than progress noise.
# "Error:" (capital E) catches raised exception lines — RuntimeError:,
# DownloadError:, GeminiBlockedError: — which "ERROR:" alone missed, leaving
# alerts with a bare "Traceback ... exit code 1" and no cause (prod 20-ago).
_ERROR_MARKERS = ("❌", "ERROR:", "Error:", "Traceback", "FATAL", "Exception",
                  "Process failed with exit code", "No metadata file generated",
                  "Execution error:")


def _job_error_text(logs) -> str:
    """The lines that explain WHY a job failed, for the alert's classifier.

    The tail of the log is usually progress noise (scene detection, ffmpeg
    banners), which made alerts blame whatever word happened to be nearby —
    a silent upload got reported as a broken download path, and a Gemini blip
    as an ffmpeg problem. Pick the error-bearing lines instead, newest last.
    """
    # Per-attempt download warnings are only noise when a later attempt
    # RECOVERED: HD-direct fails on every job (banned server IP) and a static
    # proxy takes over, yet its "Video unavailable" made whole alerts read as
    # download outages when the job actually died in Gemini. When no attempt
    # succeeded, those lines carry the real cause and must stay.
    recovered = any("Download succeeded" in ln for ln in logs)
    hits = [ln for ln in logs
            if any(m in ln for m in _ERROR_MARKERS)
            and not (recovered and "Download attempt" in ln)]
    if not hits:
        return " ".join(logs[-10:])  # nothing recognisable — fall back to the tail
    return " ".join(hits[-6:])


async def _record_job_alert(job_id):
    if not state.BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    if not job.get('user_id'):
        return  # only track managed jobs
    ok = job.get('status') == 'completed'
    err = "" if ok else _job_error_text(job.get('logs', []))
    try:
        await _alerts.record_job_outcome(ok, err)
    except Exception as e:
        print(f"⚠️  Alert recording error for {job_id}: {e}")
    await _track_job_outcome(job, ok, err)


async def _track_job_outcome(job, ok, err):
    """Report the job to OpenPanel, with the user's job index.

    The index is what makes the retention question answerable: on 26-jul-2026,
    491 of 564 users who ever processed a video did it exactly once. Counting
    distinct users at index 1 versus index >= 2 measures whether the clip
    quality work moved that, which nothing in the stack could do before.

    Client-side analytics cannot cover this: a render finishes minutes later,
    often after the tab is closed, and ad-blockers eat a share of the rest.
    """
    try:
        from cloud import analytics as _an
        from sqlalchemy import text as _sa_text
        from cloud import database as _db
        user_id = job.get('user_id')
        job_index = None
        try:
            async with _db.session() as s:
                job_index = (await s.execute(_sa_text(
                    "select count(*) from usage_ledger "
                    "where user_id = :uid and job_type = 'process'"),
                    {"uid": user_id})).scalar()
        except Exception:
            pass  # an index we cannot read is not worth failing a job over
        clips = len(((job.get('result') or {}).get('clips')) or [])
        _an.track(
            "ClipsDelivered" if ok else "JobFailed",
            user_id=user_id,
            job_index=job_index,
            clips=clips if ok else None,
            plan=job.get('user_plan'),
            source="url" if job.get('url') else "upload",
            reason=(_alerts._classify_failure(err) if not ok and err else None),
        )
    except Exception as e:
        print(f"⚠️  Analytics error: {e}")


# --- Job completion webhooks --------------------------------------------------
# Agents and pipelines (n8n, cron, MCP clients) need push, not poll: a caller
# passes webhook_url on /api/process and gets one POST when the job reaches a
# terminal state. The URL goes through assert_public_url both at submit and at
# delivery time — the second check is what defeats DNS rebinding between them.
WEBHOOK_TIMEOUT = 10.0
WEBHOOK_RETRY_DELAYS = (0, 10, 60)  # seconds before each attempt


def _sign_webhook(body: bytes, secret: str) -> str:
    import hmac as _hmac
    import hashlib as _hashlib
    return "sha256=" + _hmac.new(secret.encode(), body, _hashlib.sha256).hexdigest()


async def _webhook_clip_entries(job_id, job):
    """The payload's clip list: absolute URLs, plus durable R2 links when the
    job was archived (a webhook consumer usually fetches later, after the
    1-hour local retention would have expired the /videos path)."""
    base = (job.get('base_url') or os.environ.get("PUBLIC_API_URL", "")).rstrip("/")
    clips = (job.get('result') or {}).get('clips') or []
    entries = []
    for i, clip in enumerate(clips):
        rel = clip.get('video_url') or ""
        entries.append({
            "index": i,
            "title": clip.get('title') or clip.get('video_title_for_youtube_short'),
            "video_url": f"{base}{rel}" if rel.startswith("/") and base else rel,
        })
    if state.BILLING_ENABLED and job.get('user_id'):
        try:
            from sqlalchemy import select as _select
            from cloud.database import session as cloud_session
            from cloud.models import UserVideo
            from cloud import storage as _storage
            async with cloud_session() as s:
                vids = list((await s.execute(
                    _select(UserVideo).where(UserVideo.job_id == job_id)
                )).scalars())
            for v in vids:
                if v.clip_index is not None and v.clip_index < len(entries):
                    entries[v.clip_index]["download_url"] = _storage.presigned_get(
                        v.r2_key, expires=24 * 3600)
        except Exception as e:
            print(f"⚠️ Webhook R2 links failed for {job_id}: {e}")
    return entries


async def _deliver_webhook(url, body: bytes, secret):
    headers = {"Content-Type": "application/json", "User-Agent": "OpenShorts-Webhook/1.0"}
    if secret:
        headers["X-OpenShorts-Signature"] = _sign_webhook(body, secret)
    from security_utils import assert_public_url, UnsafeURLError
    loop = asyncio.get_event_loop()
    for attempt, delay in enumerate(WEBHOOK_RETRY_DELAYS, 1):
        if delay:
            await asyncio.sleep(delay)
        try:
            # Re-resolve on every attempt: the submit-time check is stale by now.
            await loop.run_in_executor(None, assert_public_url, url)
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT,
                                         follow_redirects=False) as client:
                resp = await client.post(url, content=body, headers=headers)
            if resp.status_code < 300:
                print(f"🪝 Webhook delivered to {url} (attempt {attempt})")
                return
            print(f"⚠️ Webhook attempt {attempt} to {url}: HTTP {resp.status_code}")
        except UnsafeURLError as e:
            print(f"🛑 Webhook URL no longer safe, dropping: {e}")
            return
        except Exception as e:
            print(f"⚠️ Webhook attempt {attempt} to {url} failed: {e}")
    print(f"❌ Webhook to {url} gave up after {len(WEBHOOK_RETRY_DELAYS)} attempts.")


async def _notify_job_webhook(job_id):
    """Fire the caller's webhook for a terminal job. Runs inside run_job_wrapper's
    finally AFTER the R2 archive, so durable links exist; the actual delivery
    (with its retry sleeps) is detached so the worker slot frees immediately."""
    job = jobs.get(job_id) or {}
    url = job.get('webhook_url')
    if not url or job.get('webhook_sent'):
        return
    job['webhook_sent'] = True
    completed = job.get('status') == 'completed'
    payload = {
        "event": "job.completed" if completed else "job.failed",
        "job_id": job_id,
        "status": job.get('status'),
        "clips": (await _webhook_clip_entries(job_id, job)) if completed else [],
    }
    if not completed:
        payload["error"] = _job_error_text(job.get('logs', []))[-500:]
    body = json.dumps(payload).encode()
    asyncio.create_task(_deliver_webhook(url, body, job.get('webhook_secret')))


async def _settle_reservation(job_id):
    if not state.BILLING_ENABLED:
        return
    job = jobs.get(job_id) or {}
    reservation_id = job.get('reservation_id')
    if not reservation_id:
        return
    try:
        if job.get('status') == 'completed':
            await cloud.metering.commit_reservation(reservation_id)
        else:
            await cloud.metering.release_reservation(reservation_id)
    except Exception as e:
        print(f"⚠️  Reservation settle error for {job_id}: {e}")
def enqueue_output(out, job_id):
    """Reads output from a subprocess and appends it to jobs logs."""
    try:
        for line in iter(out.readline, b''):
            decoded_line = _scrub_secrets(line.decode('utf-8').strip())
            if decoded_line:
                # Internal marker from main.py's downloader, not a log line.
                if decoded_line.startswith("PROXY_BYTES="):
                    try:
                        if job_id in jobs:
                            jobs[job_id]['proxy_bytes'] = int(decoded_line.split("=", 1)[1])
                    except ValueError:
                        pass
                    continue
                print(f"📝 [Job Output] {decoded_line}")
                if job_id in jobs:
                    jobs[job_id]['logs'].append(decoded_line)
    except Exception as e:
        print(f"Error reading output for job {job_id}: {e}")
    finally:
        out.close()

async def run_job(job_id, job_data):
    """Executes the subprocess for a specific job."""
    
    # A stop requested while the job sat in the queue terminates it here,
    # before any subprocess exists. The wrapper's finally still releases
    # the slot and settles the reservation.
    if jobs[job_id].get('stop_requested'):
        jobs[job_id]['status'] = 'stopped'
        jobs[job_id]["logs"].append("🛑 Generation stopped by user.")
        print(f"🛑 [run_job] {job_id} stopped while queued")
        return
    
    cmd = job_data['cmd']
    env = job_data['env']
    output_dir = job_data['output_dir']
    
    jobs[job_id]['status'] = 'processing'
    jobs[job_id]['logs'].append("Job started by worker.")
    print(f"🎬 [run_job] Executing command for {job_id}: {' '.join(cmd)}")
    
    try:
        popen_kwargs = {}
        if os.name != 'nt':
            # Own process group so a stop can kill the whole tree
            # (ffmpeg children included) instead of orphaning them.
            popen_kwargs['start_new_session'] = True
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr to stdout
            env=env,
            cwd=os.getcwd(),
            **popen_kwargs
        )
        # The stop endpoint needs this handle to terminate the tree.
        jobs[job_id]['process'] = process
        
        # We need to capture logs in a thread because Popen isn't async
        t_log = threading.Thread(target=enqueue_output, args=(process.stdout, job_id))
        t_log.daemon = True
        t_log.start()
        
        # Async wait for process with incremental updates
        start_wait = time.time()
        while process.poll() is None:
            await asyncio.sleep(2)
            
            # Check for partial results every 2 seconds
            # Look for metadata file
            try:
                json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
                if json_files:
                    target_json = json_files[0]
                    # Read metadata (it might be being written to, so simple try/except or just read)
                    # Use a lock or just robust read? json.load might fail if file is partial.
                    # Usually main.py writes it once at start (based on my review).
                    if os.path.getsize(target_json) > 0:
                        data = load_metadata(target_json)

                        base_name = metadata_base_name(target_json)
                        clips = data.get('shorts', [])
                        cost_analysis = data.get('cost_analysis')
                        
                        # Check which clips actually exist on disk
                        ready_clips = []
                        for i, clip in enumerate(clips):
                             clip_filename = f"{base_name}_clip_{i+1}.mp4"
                             clip_path = os.path.join(output_dir, clip_filename)
                             if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                                 # Checking if file is growing? For now assume if it exists and main.py moves it there, it's done.
                                 # main.py writes to temp_... then moves to final name. So presence means ready!
                                 clip['video_url'] = f"/videos/{job_id}/{clip_filename}"
                                 ready_clips.append(clip)
                        
                        if ready_clips:
                             jobs[job_id]['result'] = {'clips': ready_clips, 'cost_analysis': cost_analysis}
            except Exception as e:
                # Ignore read errors during processing
                pass

        returncode = process.returncode
        
        # A stop lands here as a killed process: report it as a user
        # action rather than running the failure classification below.
        if jobs[job_id].get('stop_requested'):
            jobs[job_id]['status'] = 'stopped'
            jobs[job_id]["logs"].append("🛑 Generation stopped by user.")
            print(f"🛑 [run_job] {job_id} stopped by user")
            return
        
        if returncode == 0:
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['logs'].append("Process finished successfully.")
            
            # Self-host: silent AWS S3 backup. Cloud mode stores to R2 instead
            # (see _archive_managed_job), so skip the redundant/paid AWS upload.
            if not state.BILLING_ENABLED:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, upload_job_artifacts, output_dir, job_id)
            
            # Find result JSON
            json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            if not json_files:
                # Backward-compat rescue if outputs were written to state.OUTPUT_DIR root
                if _relocate_root_job_artifacts(job_id, output_dir):
                    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
            if json_files:
                target_json = json_files[0]
                data = load_metadata(target_json)

                # Enhance result with video URLs
                base_name = metadata_base_name(target_json)
                clips = data.get('shorts', [])
                cost_analysis = data.get('cost_analysis')

                for i, clip in enumerate(clips):
                     clip_filename = _canonical_clip_file(output_dir, base_name, i)
                     clip['video_url'] = f"/videos/{job_id}/{clip_filename}"
                
                jobs[job_id]['result'] = {'clips': clips, 'cost_analysis': cost_analysis}
            else:
                 jobs[job_id]['status'] = 'failed'
                 jobs[job_id]['logs'].append("No metadata file generated.")
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['logs'].append(_scrub_secrets(f"Process failed with exit code {returncode}"))
            
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        # Exception text can embed URLs with credentials (e.g. the proxy URL
        # inside a yt-dlp/httpx error) — scrub before it reaches client logs.
        jobs[job_id]['logs'].append(_scrub_secrets(f"Execution error: {str(e)}"))
def _locate_source(job_id: str):
    """Find a job's source video on disk, or None.

    Upload jobs keep it in uploads/{job_id}_*; URL jobs keep the download in
    the job dir (--keep-original) under the name recorded as ``source_video``
    in metadata.json. Either way it ages out with the normal retention caps.
    """
    matches = [
        f for f in glob.glob(os.path.join(state.UPLOAD_DIR, f"{glob.escape(job_id)}_*"))
        if not os.path.basename(f).startswith("thumb_")
    ]
    if matches:
        return matches[0]
    try:
        meta_files = glob.glob(os.path.join(state.OUTPUT_DIR, job_id, "*_metadata.json"))
        if meta_files:
            with open(meta_files[0], 'r') as f:
                name = json.load(f).get('source_video')
            if name:
                candidate = os.path.join(state.OUTPUT_DIR, job_id, os.path.basename(name))
                if os.path.exists(candidate):
                    return candidate
    except Exception:
        pass
    return None
