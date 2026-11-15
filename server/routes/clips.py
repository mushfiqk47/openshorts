"""Clip editor surface: /api/edit, the EDL read, re-render, manual framing
and scenes, the Remotion render proxy, and AI effects generation."""
import os
import re
import glob
import json
import shutil
import math
import time
import uuid
import asyncio
import subprocess
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from editor import VideoEditor
from subtitles import default_font_size
import recut

from server import state
from server.state import jobs, _metering, _cloud_config
from server.billing import (
    require_managed_entitlement,
    resolve_gemini,
    gemini_missing_error,
    reserve_managed_action,
    _assert_job_owner,
)
from server.jobs import (
    _reapply_captions,
    _archive_clip_edit_bg,
    _locate_source,
    _canonical_clip_file,
    _strip_burned_captions,
    _strip_burned_hook,
)
from server.routes.process import _ensure_job_files
from core.artifacts import (  # noqa: E402
    clip_recipe_parts as _clip_recipe_parts,
    clip_window,
    load_metadata,
    metadata_base_name,
    save_metadata,
)

router = APIRouter()


class EditRequest(BaseModel):
    job_id: str
    clip_index: int
    api_key: Optional[str] = None
    input_filename: Optional[str] = None

@router.post("/api/edit")
async def edit_clip(
    req: EditRequest,
    request: Request,
):
    # Cloud (paid) mode disables BYOK: ignore any body api_key so it can't skip
    # the entitlement gate or metering (mirrors resolve_gemini ignoring the
    # header). Self-host keeps BYOK — the body key wins there.
    body_key = None if state.BILLING_ENABLED else req.api_key
    final_api_key = body_key or await resolve_gemini(request)

    if not final_api_key:
        raise gemini_missing_error()

    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[req.job_id]
    await _assert_job_owner(request, job)
    if 'result' not in job or 'clips' not in job['result']:
        raise HTTPException(status_code=400, detail="Job result not available")

    # Meter the managed Gemini call so it can't be looped for free. Skip only for
    # genuine BYOK (self-host body key) — in cloud, body_key is always None.
    edit_minutes = _cloud_config.MANAGED_ANALYSIS_MINUTES if state.BILLING_ENABLED else 0
    reservation_id = None if body_key else await reserve_managed_action(
        request, edit_minutes, req.job_id, "edit")

    try:
        # Resolve Input Path: Prefer explict input_filename from frontend (chaining edits)
        if req.input_filename:
            # Security: Ensure just a filename, no paths
            safe_name = os.path.basename(req.input_filename)
            input_path = os.path.join(state.OUTPUT_DIR, req.job_id, safe_name)
            filename = safe_name
        else:
            # Fallback to original clip
            clip = job['result']['clips'][req.clip_index]
            filename = clip['video_url'].split('/')[-1]
            input_path = os.path.join(state.OUTPUT_DIR, req.job_id, filename)
        
        if not os.path.exists(input_path):
             raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

        # Edit the clip WITHOUT its burned captions, then put them back on top —
        # otherwise the captions are baked into the edit and the next subtitle
        # pass stacks a second layer over them (see _reapply_captions).
        clean_name = _strip_burned_captions(os.path.join(state.OUTPUT_DIR, req.job_id), filename)
        had_captions = clean_name != filename
        if had_captions:
            filename = clean_name
            input_path = os.path.join(state.OUTPUT_DIR, req.job_id, clean_name)

        # Define output path for edited video
        edited_filename = f"edited_{filename}"
        output_path = os.path.join(state.OUTPUT_DIR, req.job_id, edited_filename)
        
        # Run editing in a thread to avoid blocking main loop
        # Since VideoEditor uses blocking calls (subprocess, API wait)
        def run_edit():
            editor = VideoEditor(api_key=final_api_key)
            
            # SAFE FILE RENAMING STRATEGY (Avoid UnicodeEncodeError in Docker)
            # Create a safe ASCII filename in the same directory
            safe_filename = f"temp_input_{req.job_id}.mp4"
            safe_input_path = os.path.join(state.OUTPUT_DIR, req.job_id, safe_filename)
            
            # Copy original file to safe path
            # (Copy is safer than rename if something crashes, we keep original)
            shutil.copy(input_path, safe_input_path)
            
            try:
                # 1. Upload (using safe path)
                vid_file = editor.upload_video(safe_input_path)
                
                # 2. Get duration
                import cv2
                cap = cv2.VideoCapture(safe_input_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                duration = frame_count / fps if fps else 0
                cap.release()
                
                # Load transcript from metadata
                transcript = None
                try:
                    meta_files = glob.glob(os.path.join(state.OUTPUT_DIR, req.job_id, "*_metadata.json"))
                    if meta_files:
                        transcript = load_metadata(meta_files[0]).get('transcript')
                except Exception as e:
                    print(f"⚠️ Could not load transcript for editing context: {e}")

                # 3. Get Plan (Filter String)
                # Zooms would crop burned-in captions/hooks off screen, so tell
                # the editor when the source already carries them. `filename` is
                # the original clip name (safe_input_path is an ASCII temp copy).
                has_captions = ("subtitled_" in filename) or ("hook_" in filename) or ("hooked_" in filename)
                filter_data = editor.get_ffmpeg_filter(vid_file, duration, fps=fps, width=width, height=height, transcript=transcript, has_captions=has_captions)
                
                # 4. Apply
                # Use safe output name first
                safe_output_path = os.path.join(state.OUTPUT_DIR, req.job_id, f"temp_output_{req.job_id}.mp4")
                editor.apply_edits(safe_input_path, safe_output_path, filter_data)
                
                # Move result to final destination (rename works even if dest name has unicode if filesystem supports it, 
                # but python might still struggle if locale is broken? No, os.rename usually handles it better than subprocess args)
                # Actually, output_path is defined above: f"edited_{filename}"
                # If filename has unicode, output_path has unicode.
                # Let's hope shutil.move / os.rename works.
                if os.path.exists(safe_output_path):
                    shutil.move(safe_output_path, output_path)
                
                return filter_data
            finally:
                # Cleanup temp safe input
                if os.path.exists(safe_input_path):
                    os.remove(safe_input_path)

        # Run in thread pool
        loop = asyncio.get_event_loop()
        plan = await loop.run_in_executor(None, run_edit)

        # Captions back on top, so the clip the user sees keeps them and the
        # clean edited file stays available for a later restyle.
        if had_captions:
            recap = await loop.run_in_executor(
                None, _reapply_captions, req.job_id, req.clip_index, output_path)
            if recap:
                edited_filename = os.path.basename(recap)

        new_video_url = f"/videos/{req.job_id}/{edited_filename}"

        # Persist the new current file like /api/subtitle does: in-memory job
        # result + metadata.json, so reload/recovery/re-archive see this version.
        if req.clip_index < len(job['result']['clips']):
            job['result']['clips'][req.clip_index]['video_url'] = new_video_url
        try:
            meta_files = glob.glob(os.path.join(state.OUTPUT_DIR, req.job_id, "*_metadata.json"))
            if meta_files:
                meta = load_metadata(meta_files[0])
                shorts = meta.get('shorts', [])
                if req.clip_index < len(shorts):
                    shorts[req.clip_index]['video_url'] = new_video_url
                    meta['shorts'] = shorts
                    save_metadata(meta_files[0], meta)
        except Exception as e:
            print(f"⚠️ Failed to update metadata.json: {e}")

        _archive_clip_edit_bg(req.job_id, req.clip_index, edited_filename)

        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        return {
            "success": True,
            "new_video_url": new_video_url,
            "edit_plan": plan
        }

    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        print(f"❌ Edit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/api/clip/{job_id}/{clip_index}/transcript")
async def get_clip_transcript(job_id: str, clip_index: int, request: Request):
    """Return word-level captions for a specific clip, formatted for Remotion."""
    await _ensure_job_files(job_id, request)
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    await _assert_job_owner(request, jobs[job_id])
    output_dir = os.path.join(state.OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))

    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")

    data = load_metadata(json_files[0])

    transcript = data.get('transcript')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata")

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    clip_data = clips[clip_index]

    # Recut clips are concatenations of source segments; clip_window remaps
    # the transcript onto the clip timeline so every consumer keeps its flat
    # start..end logic.
    transcript, clip_start, clip_end = clip_window(transcript, clip_data)

    # Extract words within clip range and convert to CaptionWord format
    captions = []
    for segment in transcript.get('segments', []):
        for word_info in segment.get('words', []):
            if word_info['end'] > clip_start and word_info['start'] < clip_end:
                captions.append({
                    "text": word_info.get('word', '').strip(),
                    "startMs": int((max(0, word_info['start'] - clip_start)) * 1000),
                    "endMs": int((max(0, word_info['end'] - clip_start)) * 1000),
                })

    duration_sec = clip_end - clip_start

    return {
        "captions": captions,
        "durationSec": duration_sec,
        "language": transcript.get('language', 'en'),
        # The subtitle modal previews at this size and burns with it too, so
        # the preview matches the exported file (CAPTION_FONT_SIZE from .env).
        "defaultFontSize": default_font_size(),
    }


# --- Clip editor: EDL + re-render ---

# The editor ships the WHOLE source transcript, not a window around the clip:
# the point of the source track is extending a cut into material the clip never
# covered, and you cannot pick a new in-point from words you were not sent.
# Cost is about 7 KB of JSON per minute of speech, fetched once per editor open.


def _source_duration_seconds(path):
    """Probe a video's duration; None when it can't be read."""
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        # OpenCV reports -1/-1 for files it can't read — a naive truthiness
        # check would turn that into a phantom 1.0s duration.
        if fps > 0 and frames > 0:
            return round(frames / fps, 3)
    except Exception:
        pass
    return None


@router.get("/api/clip/{job_id}/{clip_index}/edl")
async def get_clip_edl(job_id: str, clip_index: int, request: Request):
    """The clip's editable recipe: which source segments it was cut from, the
    word timeline around them, and whether the source is still available for
    cuts outside the original range."""
    await _ensure_job_files(job_id, request)
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    await _assert_job_owner(request, job)

    output_dir = os.path.join(state.OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")
    data = load_metadata(json_files[0])

    clips = data.get('shorts', [])
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
    clip = clips[clip_index]

    segments, canonical_range = _clip_recipe_parts(clip)
    transcript = data.get('transcript') or {}
    words = recut.transcript_words(transcript)

    source_path = _locate_source(job_id)
    source_duration = _source_duration_seconds(source_path) if source_path else None
    duration_estimated = source_duration is None
    if duration_estimated:
        # Best remaining scale for the source track: the last spoken word or
        # the furthest point any recipe touches.
        candidates = [canonical_range['end']] + [s['end'] for s in segments]
        if words:
            candidates.append(words[-1]['e'])
        source_duration = round(max(candidates), 3)

    words_out = [
        {"w": w["w"], "s": round(w["s"], 3), "e": round(w["e"], 3)}
        for w in words
    ]

    current_file = (clip.get('video_url') or '').split('/')[-1]
    if not current_file:
        base_name = metadata_base_name(json_files[0])
        current_file = _canonical_clip_file(output_dir, base_name, clip_index)

    total = recut.total_duration(segments)
    return {
        "job_id": job_id,
        "clip_index": clip_index,
        "title": clip.get('video_title_for_youtube_short') or '',
        "segments": segments,
        "framing": (clip.get('recipe') or {}).get('framing') or 'auto',
        "canonical_range": canonical_range,
        "duration": total,
        "current_file": current_file,
        "has_captions": bool(re.match(r'^subtitled_\d+_', current_file)),
        "words": words_out,
        "source": {
            "available": bool(source_path),
            "url": f"/api/source/{job_id}" if source_path else None,
            "duration": source_duration,
            "duration_estimated": duration_estimated,
        },
        "limits": {
            "max_segments": recut.MAX_SEGMENTS,
            "min_segment_seconds": recut.MIN_SEGMENT_SECONDS,
            "max_total_seconds": recut.MAX_TOTAL_SECONDS,
        },
        "rerender_minutes": (max(1, math.ceil(total / 60.0))
                             if state.BILLING_ENABLED else 0),
    }


class RerenderSegment(BaseModel):
    start: float
    end: float


class RerenderRequest(BaseModel):
    job_id: str
    clip_index: int
    segments: List[RerenderSegment]
    snap_to_words: bool = False
    reapply_captions: bool = True
    # None = inherit the recipe's framing (so plain trims keep the look);
    # 'auto' resets to the classifier; 'full'/'track' force a layout.
    framing: Optional[str] = None


# Manual framing -> reframe-engine strategy. 'full' shows the whole source
# frame (WIDE: no side-cropping, blurred filler bands); 'track' forces the
# subject-tracking crop. Anything non-auto needs the retained source video.
_FRAMING_STRATEGIES = {"auto": None, "full": "WIDE", "track": "TRACK"}


# One lock per job (same pattern as _restore_locks): rerenders on the same job
# share metadata.json and the canonical files, so they must not interleave.
_rerender_locks: Dict[str, asyncio.Lock] = {}

# Scene-listing builds write stable preview/thumbnail names per job; serialize
# them so overlapping editor opens don't tear each other's files.
_scenes_locks: Dict[str, asyncio.Lock] = {}


@router.post("/api/clip/rerender")
async def rerender_clip(req: RerenderRequest, request: Request):
    """Re-render a clip from an edited EDL (the clip editor's save button).

    Two paths, chosen automatically:
    - FAST: every segment stays inside the range the canonical clip was cut
      from → recut straight from the already-reframed canonical file. No ML,
      no source needed.
    - SOURCE: a segment reaches outside → recut from the retained source and
      re-reframe with the same engine the pipeline used. 409 when the source
      already aged out.
    """
    await require_managed_entitlement(request)
    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[req.job_id]
    await _assert_job_owner(request, job)

    # Serialize rerenders per job: concurrent saves (easy for an MCP agent to
    # produce) would otherwise race on the shared metadata.json
    # read-modify-write below, with the last writer silently reverting the
    # other clip's recipe/video_url.
    lock = _rerender_locks.setdefault(req.job_id, asyncio.Lock())
    async with lock:
        return await _rerender_locked(req, request, job)


async def _rerender_locked(req: RerenderRequest, request: Request, job):
    output_dir = os.path.join(state.OUTPUT_DIR, req.job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")
    data = load_metadata(json_files[0])

    clips = data.get('shorts', [])
    if req.clip_index < 0 or req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
    clip = clips[req.clip_index]
    transcript = data.get('transcript') or {}

    base_name = metadata_base_name(json_files[0])
    clean_name = f"{base_name}_clip_{req.clip_index + 1}.mp4"
    canonical_path = os.path.join(output_dir, clean_name)

    _, canonical_range = _clip_recipe_parts(clip)
    source_path = _locate_source(req.job_id)
    source_duration = _source_duration_seconds(source_path) if source_path else None

    framing = req.framing or (clip.get('recipe') or {}).get('framing') or 'auto'
    if framing not in _FRAMING_STRATEGIES:
        raise HTTPException(status_code=400,
                            detail="framing must be one of: auto, full, track")
    force_strategy = _FRAMING_STRATEGIES[framing]

    try:
        segments = recut.normalize_segments(
            [{"start": s.start, "end": s.end} for s in req.segments],
            source_duration)
        if req.snap_to_words:
            snap_bound = source_duration or max(s['end'] for s in segments)
            segments = recut.snap_segments(segments, transcript, snap_bound)
            if not source_path:
                # Snapping trails into silence and may nudge a boundary past
                # the canonical range; without a source the fast path is the
                # only path, so clamp back instead of failing with a 409.
                segments = [
                    {"start": round(max(s['start'], canonical_range['start']), 3),
                     "end": round(min(s['end'], canonical_range['end']), 3)}
                    for s in segments]
            # Re-validate after snapping/clamping: a segment fully outside the
            # canonical range clamps to an inverted (end < start) window, and
            # snapping can stretch the total past the cap. Without this it
            # reaches ffmpeg and dies as a 500 instead of a clean 400.
            segments = recut.normalize_segments(segments, source_duration)
    except recut.RecutError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # A framing override always re-reframes from the source: the canonical file
    # has the old layout baked into its pixels.
    fast = (force_strategy is None
            and os.path.exists(canonical_path)
            and recut.within_range(segments, canonical_range['start'],
                                   canonical_range['end']))
    if not fast and not source_path:
        raise HTTPException(
            status_code=409,
            detail=("The source video is no longer on the server; changing the "
                    "framing needs it." if force_strategy is not None else
                    "The source video is no longer on the server, so segments "
                    "must stay within the original clip range."))

    total = recut.total_duration(segments)
    rerender_minutes = (max(1, math.ceil(total / 60.0))
                        if state.BILLING_ENABLED else 0)
    reservation_id = await reserve_managed_action(
        request, rerender_minutes, req.job_id, "rerender")

    v_transcript = (recut.virtual_transcript(transcript, segments)
                    if req.reapply_captions else None)

    def run_recut():
        if fast:
            return recut.perform_recut(
                input_path=canonical_path,
                segments=recut.rebase_segments(
                    segments, canonical_range['start'], canonical_range['end']),
                output_dir=output_dir, clean_name=clean_name,
                reframe=False, captions_transcript=v_transcript)
        return recut.perform_recut(
            input_path=source_path, segments=segments,
            output_dir=output_dir, clean_name=clean_name,
            reframe=True, output_format=data.get('output_format', 'auto'),
            watermark=bool(job.get('watermark')),
            force_strategy=force_strategy,
            captions_transcript=v_transcript)

    try:
        loop = asyncio.get_event_loop()
        served_name, _clean_recut_name = await loop.run_in_executor(None, run_recut)

        new_video_url = f"/videos/{req.job_id}/{served_name}"
        new_recipe = {"v": 1, "segments": segments,
                      "canonical_range": canonical_range}
        if framing != 'auto':
            new_recipe["framing"] = framing
        # Covering range, deliberately not segments[0]/segments[-1]: segments
        # may legally be out of source order, and downstream consumers only
        # need a sane positive window (the recipe is the real timeline).
        new_start = min(s['start'] for s in segments)
        new_end = max(s['end'] for s in segments)

        updates = {'video_url': new_video_url, 'start': new_start,
                   'end': new_end, 'recipe': new_recipe}
        # Per-scene manual framing is keyed by scene indices of a specific cut;
        # this render neither applied it nor can it survive a changed cut, so
        # clear it rather than let /scenes serve stale overrides against the
        # wrong shots (re-frame after trimming to re-apply by hand).
        if clip.get('crop_overrides'):
            updates['crop_overrides'] = None
        clip.update(updates)
        data['shorts'] = clips
        save_metadata(json_files[0], data, indent=2)
        mem_clips = (job.get('result') or {}).get('clips') or []
        if req.clip_index < len(mem_clips):
            mem_clips[req.clip_index].update(updates)

        _archive_clip_edit_bg(req.job_id, req.clip_index, served_name)
        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        return {
            "success": True,
            "new_video_url": new_video_url,
            "recipe": new_recipe,
            "framing": framing,
            "start": new_start,
            "end": new_end,
            "duration": total,
            "render_path": "fast" if fast else "source",
        }
    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        print(f"❌ Rerender Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Manual framing -----------------------------------------------------------
#
# The reframe engine picks the crop automatically, and on a podcast it is right
# most of the time and grossly wrong occasionally: a wide shot of the whole
# table averages over one face, so the scene falls to GENERAL (letterboxed) or
# tracks the wrong person. There was no way to say "no, frame it here".
#
# The unit is the SCENE, not the clip, because a podcast cuts between a fixed
# close camera and a fixed wide one, and the right crop differs per camera.
# Scene boundaries already are the camera changes: PySceneDetect finds them.
#
# Scenes the user never touches keep the automatic camera, so correcting one
# bad shot cannot spoil the ones the tracker got right.

class ReframeRequest(BaseModel):
    job_id: str
    clip_index: int
    # scene index (string key, JSON-style) -> either a crop centre as a
    # fraction of the source width, or {"top": f, "bottom": f} to stack two
    # regions. Fractions travel instead of pixels so the editor never needs to
    # know the source dimensions.
    crop_overrides: Dict[str, Any]
    reapply_captions: bool = True


def _clip_scene_workfile(source_path, segments, output_dir, token):
    """Cut the clip out of the source so scenes can be detected on it.

    The name is unique per call, unlike the thumbnails and the preview: two
    editor opens on the same clip would otherwise write the same temp file at
    once, and the first to finish deletes it out from under the second.
    """
    work_path = os.path.join(output_dir, f"scenes_{token}.mp4")
    recut.run_cut_concat(source_path, segments, work_path, output_dir)
    return work_path


@router.get("/api/clip/{job_id}/{clip_index}/scenes")
async def get_clip_scenes(job_id: str, clip_index: int, request: Request):
    """Scenes of a clip, each with a SOURCE frame to frame it against.

    The frames come from the uncropped cut, not the delivered clip: the point
    is to show what the automatic crop threw away, which the 9:16 file no
    longer contains.
    """
    # Entitlement too, not just ownership: listing scenes cuts the clip from
    # source, runs scene detection and encodes a preview — real compute.
    await require_managed_entitlement(request)
    await _ensure_job_files(job_id, request)
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    await _assert_job_owner(request, job)

    output_dir = os.path.join(state.OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")
    data = load_metadata(json_files[0])

    clips = data.get('shorts', [])
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    if data.get('output_format') == 'horizontal':
        raise HTTPException(
            status_code=400,
            detail="Horizontal clips keep the full frame; there is no crop to reframe.")

    clip = clips[clip_index]
    segments, _canonical_range = _clip_recipe_parts(clip)
    # What was applied last time. Without this the editor reopens blank, and
    # since a re-render rebuilds from source using ONLY what it is sent, the
    # next save would silently drop every earlier adjustment.
    saved_overrides = clip.get('crop_overrides') or {}
    source_path = _locate_source(job_id)
    if not source_path:
        raise HTTPException(
            status_code=409,
            detail="The source video is no longer on the server, so the "
                   "framing of this clip can no longer be changed.")

    def build():
        import cv2
        import main as m

        # Stable for the files the browser fetches (no accumulation), unique
        # for the temp cut (no collision between overlapping requests).
        # temp_ prefix keeps these editor-only artifacts out of the self-host
        # S3 backup (it skips temp_*); stable names still avoid accumulation.
        token = str(clip_index)
        work_token = f"{clip_index}_{uuid.uuid4().hex[:8]}"
        preview_name = f"temp_preview_{clip_index}.mp4"
        preview_path = os.path.join(output_dir, preview_name)
        work_path = _clip_scene_workfile(source_path, segments, output_dir, work_token)
        try:
            scenes, fps = m.detect_scenes(work_path)
            fps = float(fps) or 30.0
            orig_w, orig_h = m.get_video_resolution(work_path)

            cap = cv2.VideoCapture(work_path)
            if not scenes:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
                bounds = [(0, total)]
            else:
                bounds = [(s.get_frames(), e.get_frames()) for s, e in scenes]

            out = []
            for idx, (start_f, end_f) in enumerate(bounds):
                mid = (start_f + end_f) // 2
                cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
                ok, frame = cap.read()
                thumb_name = f"temp_scene_{token}_{idx:03d}.jpg"
                suggested = 0.5
                suggested_y = 0.5
                if ok:
                    cv2.imwrite(os.path.join(output_dir, thumb_name), frame,
                                [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    # Start the rectangle on the biggest face in the shot, so
                    # the common case is a nudge rather than a hunt.
                    try:
                        faces = m.detect_face_candidates(frame)
                        if faces:
                            box = max(faces,
                                      key=lambda f: f['box'][2] * f['box'][3])['box']
                            suggested = min(1.0, max(0.0,
                                                     (box[0] + box[2] / 2) / orig_w))
                            # SPLIT halves crop vertically too, so the face's
                            # height matters there (TRACK ignores it).
                            suggested_y = min(1.0, max(0.0,
                                                       (box[1] + box[3] / 2) / orig_h))
                    except Exception:
                        pass
                else:
                    thumb_name = None

                out.append({
                    "index": idx,
                    "start": round(start_f / fps, 3),
                    "end": round(end_f / fps, 3),
                    "thumbnail_url": (f"/videos/{job_id}/{thumb_name}"
                                      if thumb_name else None),
                    "suggested_center": round(suggested, 4),
                    "suggested_center_y": round(suggested_y, 4),
                })
            cap.release()
            return orig_w, orig_h, out, preview_name
        finally:
            # The uncropped cut becomes a light preview instead of being
            # discarded: judging the framing means knowing who is talking, and
            # the delivered 9:16 file no longer shows the rest of the room.
            try:
                if os.path.exists(work_path):
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-i", work_path,
                         "-vf", "scale=640:-2", "-c:v", "libx264", "-preset",
                         "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "96k",
                         # faststart: the editor's <video> streams the preview;
                         # a tail moov would stall it until fully downloaded.
                         "-movflags", "+faststart",
                         preview_path], check=True, timeout=600)
            except Exception as exc:
                print(f"Scene preview failed: {exc}")
            finally:
                if os.path.exists(work_path):
                    os.remove(work_path)

    # Serialized per job: two overlapping opens would run two ffmpeg writers
    # on the same stable preview/thumbnail names and serve a torn file.
    lock = _scenes_locks.setdefault(job_id, asyncio.Lock())
    async with lock:
        try:
            loop = asyncio.get_event_loop()
            orig_w, orig_h, scenes_out, preview_name = await loop.run_in_executor(None, build)
        except Exception as e:
            print(f"Scene listing error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Width of the crop window as a fraction of the source width: the editor
    # draws the rectangle with it and needs no pixel arithmetic of its own.
    # The aspect follows the job's output format (9:16, or 1:1 for square).
    aspect = 1.0 if data.get('output_format') == 'square' else 9.0 / 16.0
    crop_w = min(orig_w, orig_h * aspect)
    return {
        "job_id": job_id,
        "clip_index": clip_index,
        "source_width": orig_w,
        "source_height": orig_h,
        "crop_width_fraction": round(crop_w / orig_w, 4),
        "preview_url": f"/videos/{job_id}/{preview_name}",
        "saved_overrides": saved_overrides,
        "scenes": scenes_out,
    }


@router.post("/api/clip/reframe")
async def reframe_clip(req: ReframeRequest, request: Request):
    """Re-render a clip with hand-framed scenes, leaving its cut untouched.

    Deliberately separate from /api/clip/rerender: the overrides are keyed by
    scene index, and a scene index only means anything against a given cut. If
    framing rode along with a trim save, changing the trim would silently move
    every override onto the wrong shot.
    """
    await require_managed_entitlement(request)
    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[req.job_id]
    await _assert_job_owner(request, job)

    def _fraction(v):
        return min(1.0, max(0.0, float(v)))

    overrides = {}
    for key, value in (req.crop_overrides or {}).items():
        try:
            idx = int(key)
            if isinstance(value, dict):
                def _half(h):
                    if isinstance(h, dict):
                        return {"x": _fraction(h["x"]), "y": _fraction(h.get("y", 0.5))}
                    return {"x": _fraction(h), "y": 0.5}
                overrides[idx] = {"top": _half(value["top"]),
                                  "bottom": _half(value["bottom"])}
            else:
                overrides[idx] = _fraction(value)
        except (KeyError, TypeError, ValueError):
            continue
    if not overrides:
        raise HTTPException(status_code=400,
                            detail="No scene framing was provided.")

    # Same lock as /rerender: both read-modify-write the job's metadata.json,
    # and the metadata must be read INSIDE the lock or a rerender committing
    # in between gets clobbered by a write of stale data.
    lock = _rerender_locks.setdefault(req.job_id, asyncio.Lock())
    async with lock:
        return await _reframe_locked(req, request, job, overrides)


async def _reframe_locked(req: ReframeRequest, request: Request, job, overrides):
    output_dir = os.path.join(state.OUTPUT_DIR, req.job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")
    data = load_metadata(json_files[0])

    clips = data.get('shorts', [])
    if req.clip_index < 0 or req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
    clip = clips[req.clip_index]

    if data.get('output_format') == 'horizontal':
        raise HTTPException(
            status_code=400,
            detail="Horizontal clips keep the full frame; there is no crop to reframe.")

    segments, canonical_range = _clip_recipe_parts(clip)
    source_path = _locate_source(req.job_id)
    if not source_path:
        raise HTTPException(
            status_code=409,
            detail="The source video is no longer on the server, so the "
                   "framing of this clip can no longer be changed.")

    # Whole-clip framing (recipe.framing, the clip editor's selector) still
    # applies to the scenes the user did NOT hand-position: apply_crop_overrides
    # runs after force_strategy, so a per-scene choice beats the whole-clip one.
    framing = (clip.get('recipe') or {}).get('framing') or 'auto'
    force_strategy = _FRAMING_STRATEGIES.get(framing)

    # A reframe re-renders the full cut from source — same work as a source-path
    # rerender, so it meters the same.
    total = recut.total_duration(segments)
    rerender_minutes = (max(1, math.ceil(total / 60.0))
                        if state.BILLING_ENABLED else 0)
    reservation_id = await reserve_managed_action(
        request, rerender_minutes, req.job_id, "reframe")

    # Every default clip ships with burned captions; re-rendering without them
    # would silently hand back a caption-less file.
    v_transcript = (recut.virtual_transcript(data.get('transcript') or {}, segments)
                    if req.reapply_captions else None)

    base_name = metadata_base_name(json_files[0])
    # The CLEAN base name, exactly as /api/clip/rerender does — never the
    # current derived file. perform_recut prefixes whatever it is given, so
    # feeding it the newest derivative made every re-render add another
    # recut_<ts>_<hex>_ in front of the previous one. A few rounds of framing
    # and captioning and the path blew past the filesystem limit:
    # "Error opening output ...: File name too long".
    clean_name = f"{base_name}_clip_{req.clip_index + 1}.mp4"

    def run():
        return recut.perform_recut(
            input_path=source_path, segments=segments,
            output_dir=output_dir, clean_name=clean_name,
            reframe=True, output_format=data.get('output_format', 'auto'),
            watermark=bool(job.get('watermark')),
            force_strategy=force_strategy,
            crop_overrides=overrides,
            captions_transcript=v_transcript)

    try:
        loop = asyncio.get_event_loop()
        served_name, _clean = await loop.run_in_executor(None, run)

        new_video_url = f"/videos/{req.job_id}/{served_name}"
        new_recipe = {"v": 1, "segments": segments,
                      "canonical_range": canonical_range}
        if framing != 'auto':
            new_recipe["framing"] = framing
        updates = {
            'video_url': new_video_url,
            'recipe': new_recipe,
            'crop_overrides': {str(k): v for k, v in overrides.items()},
        }
        clip.update(updates)
        data['shorts'] = clips
        save_metadata(json_files[0], data, indent=2)
        mem_clips = (job.get('result') or {}).get('clips') or []
        if req.clip_index < len(mem_clips):
            mem_clips[req.clip_index].update(updates)

        _archive_clip_edit_bg(req.job_id, req.clip_index, served_name)
        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        # The cut is untouched, but the response mirrors /rerender's shape
        # so the dashboard can reuse one handler without clearing the
        # clip's timing fields.
        return {
            "success": True,
            "new_video_url": new_video_url,
            "recipe": new_recipe,
            "start": min(s['start'] for s in segments),
            "end": max(s['end'] for s in segments),
            "framed_scenes": sorted(overrides),
        }
    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        print(f"Reframe Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Remotion Render Proxy ---
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "http://renderer:3100")

@router.post("/api/render")
async def proxy_render(request: Request):
    """Proxy render requests to the Node.js Remotion render service."""
    await require_managed_entitlement(request)
    import httpx
    body = await request.json()
    render_minutes = _cloud_config.RENDER_MINUTES if state.BILLING_ENABLED else 0
    reservation_id = await reserve_managed_action(
        request, render_minutes, str(uuid.uuid4()), "render")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{RENDER_SERVICE_URL}/render", json=body)
        result = resp.json()
        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        return result
    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        raise HTTPException(status_code=502, detail=f"Render service unavailable: {e}")

@router.get("/api/render/{render_id}")
async def proxy_render_status(render_id: str):
    """Proxy render status polling to the Node.js Remotion render service."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{RENDER_SERVICE_URL}/render/{render_id}")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Render service unavailable: {e}")


class EffectsGenerateRequest(BaseModel):
    job_id: str
    clip_index: int
    input_filename: Optional[str] = None

@router.post("/api/effects/generate")
async def generate_effects_config(
    req: EffectsGenerateRequest,
    request: Request,
):
    """Generate structured EffectsConfig JSON for Remotion rendering via Gemini AI."""
    final_api_key = await resolve_gemini(request)

    if not final_api_key:
        raise gemini_missing_error()

    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[req.job_id]
    await _assert_job_owner(request, job)
    if 'result' not in job or 'clips' not in job['result']:
        raise HTTPException(status_code=400, detail="Job result not available")

    # Meter the managed Gemini call (no-op for self-host).
    fx_minutes = _cloud_config.MANAGED_ANALYSIS_MINUTES if state.BILLING_ENABLED else 0
    reservation_id = await reserve_managed_action(request, fx_minutes, req.job_id, "effects")

    try:
        # Resolve input path
        if req.input_filename:
            safe_name = os.path.basename(req.input_filename)
            input_path = os.path.join(state.OUTPUT_DIR, req.job_id, safe_name)
        else:
            clip = job['result']['clips'][req.clip_index]
            filename = clip['video_url'].split('/')[-1]
            input_path = os.path.join(state.OUTPUT_DIR, req.job_id, filename)

        if not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

        def run_effects_generation():
            editor = VideoEditor(api_key=final_api_key)

            # Create safe ASCII filename to avoid encoding issues
            safe_filename = f"temp_effects_{req.job_id}.mp4"
            safe_input_path = os.path.join(state.OUTPUT_DIR, req.job_id, safe_filename)
            shutil.copy(input_path, safe_input_path)

            try:
                # Upload video to Gemini
                vid_file = editor.upload_video(safe_input_path)

                # Get video metadata via ffprobe
                probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,r_frame_rate,duration',
                    '-show_entries', 'format=duration',
                    '-of', 'json',
                    safe_input_path
                ]
                probe_result = subprocess.check_output(probe_cmd).decode().strip()
                probe_data = json.loads(probe_result)

                stream = probe_data.get('streams', [{}])[0]
                width = int(stream.get('width', 1080))
                height = int(stream.get('height', 1920))

                # Parse fps from r_frame_rate (e.g. "30/1")
                r_frame_rate = stream.get('r_frame_rate', '30/1')
                num, den = r_frame_rate.split('/')
                fps = round(int(num) / int(den), 2)

                # Get duration from stream or format
                duration = float(stream.get('duration', 0))
                if duration == 0:
                    duration = float(probe_data.get('format', {}).get('duration', 0))

                # Load transcript from metadata
                transcript = None
                try:
                    meta_files = glob.glob(os.path.join(state.OUTPUT_DIR, req.job_id, "*_metadata.json"))
                    if meta_files:
                        transcript = load_metadata(meta_files[0]).get('transcript')
                except Exception as e:
                    print(f"⚠️ Could not load transcript for effects config: {e}")

                # Generate effects config
                effects_config = editor.get_effects_config(
                    vid_file, duration, fps=fps, width=width, height=height, transcript=transcript
                )

                return effects_config
            finally:
                if os.path.exists(safe_input_path):
                    os.remove(safe_input_path)

        loop = asyncio.get_event_loop()
        effects_config = await loop.run_in_executor(None, run_effects_generation)

        if effects_config is None:
            raise HTTPException(status_code=500, detail="Failed to generate effects config from Gemini")

        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        return {"effects": effects_config}

    except HTTPException:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        raise
    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        print(f"❌ Effects Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
