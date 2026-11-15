"""Caption / hook / dubbing surface: /api/subtitle(/remove), /api/hook,
and /api/translate."""
import os
import re
import glob
import time
import asyncio
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from subtitles import generate_srt, generate_ass, burn_subtitles, generate_srt_from_video
from hooks import add_hook_to_video
from translate import translate_video, get_supported_languages

from server import state
from server.state import jobs, _metering, _cloud_config
from server.billing import require_managed_entitlement, _assert_job_owner
from server.jobs import _reapply_captions, _archive_clip_edit_bg, _strip_burned_captions, _strip_burned_hook
from server.routes.process import _ensure_job_files
from core.artifacts import (  # noqa: E402
    clip_window,
    load_metadata,
    metadata_base_name,
    save_metadata,
)

router = APIRouter()

class CaptionWordIn(BaseModel):
    """One user-edited caption word, clip-relative ms — the same shape the
    /transcript endpoint hands the subtitle modal."""
    text: str
    startMs: int
    endMs: int


class SubtitleRequest(BaseModel):
    job_id: str
    clip_index: int
    position: str = "bottom" # top, middle, bottom
    font_size: int = 16
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    style: str = "classic"  # classic (uniform color) or karaoke (word highlight)
    highlight_color: str = "#FFD700"
    effect: str = "none"  # none | glow | pop | box (karaoke only)
    base_opacity: float = 1.0  # opacity of non-active words (dimmed modern look)
    uppercase: bool = False
    input_filename: Optional[str] = None
    # User-edited caption words. When present, the burn uses them VERBATIM
    # instead of regenerating from the stored transcript — without this, text
    # edits in the modal were silently discarded on the server render path.
    words: Optional[List[CaptionWordIn]] = None
@router.post("/api/subtitle")
async def add_subtitles(req: SubtitleRequest, request: Request):
    await require_managed_entitlement(request)
    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Reload job data from disk just in case metadata was updated
    job = jobs[req.job_id]
    await _assert_job_owner(request, job)

    # We need to access metadata.json to get the transcript
    output_dir = os.path.join(state.OUTPUT_DIR, req.job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))

    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")

    data = load_metadata(json_files[0])
    
    transcript = data.get('transcript')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata. Please process a new video.")
        
    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
        
    clip_data = clips[req.clip_index]

    # Recut clips concatenate several source segments, so clip_window restyles
    # against the clip-relative remapped transcript instead of the flat range.
    sub_transcript, sub_start, sub_end = clip_window(transcript, clip_data)

    # User-edited captions win over both: build a synthetic clip-relative
    # transcript from them so the SRT/ASS generators burn the edited words
    # verbatim (issue #69 — edits used to be dropped on this path).
    if req.words:
        if len(req.words) > 2000:
            raise HTTPException(status_code=400, detail="Too many caption words (max 2000).")
        # Leading space = Whisper's word-boundary convention; without it the
        # block collector treats each word as a continuation fragment and
        # glues the whole line together.
        edited = [
            {"word": " " + w.text.strip(), "start": max(0.0, w.startMs / 1000.0),
             "end": max(0.0, w.endMs / 1000.0)}
            for w in req.words if w.text.strip() and w.endMs > w.startMs >= 0
        ]
        if edited:
            edited.sort(key=lambda w: w["start"])
            sub_transcript = {
                "language": (transcript or {}).get("language", "en"),
                "segments": [{
                    "start": edited[0]["start"], "end": edited[-1]["end"],
                    "text": " ".join(w["word"] for w in edited),
                    "words": edited,
                }],
            }
            sub_start, sub_end = 0.0, max(w["end"] for w in edited)

    # Video Path
    if req.input_filename:
        # Use chained file
        filename = os.path.basename(req.input_filename)
    else:
        # Fallback to standard naming
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = metadata_base_name(json_files[0])
             filename = f"{base_name}_clip_{req.clip_index+1}.mp4"

    # Re-subtitling must replace previous subtitles instead of burning over them.
    filename = _strip_burned_captions(output_dir, filename)

    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path):
        # Try looking for edited version if url implied it?
        # Just fail if not found.
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    # Define outputs
    generation_id = int(time.time())
    is_karaoke = req.style == "karaoke"
    srt_filename = f"subs_{req.clip_index}_{generation_id}.{'ass' if is_karaoke else 'srt'}"
    srt_path = os.path.join(output_dir, srt_filename)

    # Style options shared by the karaoke ASS generator paths.
    karaoke_opts = dict(
        alignment=req.position, fontsize=req.font_size, font_name=req.font_name,
        font_color=req.font_color, border_color=req.border_color,
        border_width=req.border_width, highlight_color=req.highlight_color,
        bg_color=req.bg_color, bg_opacity=req.bg_opacity,
        effect=req.effect, base_opacity=req.base_opacity, uppercase=req.uppercase,
    )

    # Output video
    # We create a new file "subtitled_..."
    output_filename = f"subtitled_{generation_id}_{filename}"
    output_path = os.path.join(output_dir, output_filename)

    # Burning captions is FREE. They're table stakes for short-form — a clip
    # without them barely works on any platform — and the cost is nil: the SRT
    # comes from the transcript already sitting in metadata.json, and the burn is
    # a single short FFmpeg pass (4s on CPU for a 12s clip, 1-2s on the GPU).
    # Charging 2 minutes for that meant 10% of the whole free monthly quota per
    # captioned clip, roughly what generating the clip cost in the first place —
    # so people skipped it: only 9% of delivered clips had captions (prod audit,
    # 25-jul-2026). The endpoint is already gated by require_managed_entitlement
    # above, so this is not an open door.
    #
    # The dubbed path is the exception and keeps the charge: it runs a fresh
    # ASR over the translated audio, which is real work.
    is_dubbed = filename.startswith("translated_")
    subtitle_minutes = (_cloud_config.subtitle_minutes_for(filename)
                        if state.BILLING_ENABLED else 0)
    reservation_id = await reserve_managed_action(
        request, subtitle_minutes, req.job_id, "subtitle")

    try:
        # 1. Generate SRT — from the existing transcript, or a fresh
        # transcription when the audio was dubbed (see the metering note above).
        if is_dubbed:
            print(f"🎙️ Dubbed video detected, transcribing audio for subtitles...")
            def run_transcribe_srt():
                if is_karaoke:
                    return generate_srt_from_video(input_path, srt_path, style="karaoke", **karaoke_opts)
                return generate_srt_from_video(input_path, srt_path)

            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, run_transcribe_srt)
        elif is_karaoke:
            success = generate_ass(sub_transcript, sub_start, sub_end, srt_path, **karaoke_opts)
        else:
            success = generate_srt(sub_transcript, sub_start, sub_end, srt_path)

        if not success:
             raise HTTPException(status_code=400, detail="No words found for this clip range.")

        # 2. Burn Subtitles
        # Run in thread pool
        def run_burn():
             burn_subtitles(input_path, srt_path, output_path,
                           alignment=req.position, fontsize=req.font_size,
                           font_name=req.font_name, font_color=req.font_color,
                           border_color=req.border_color, border_width=req.border_width,
                           bg_color=req.bg_color, bg_opacity=req.bg_opacity)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_burn)
        
    except Exception as e:
        print(f"❌ Subtitle Error: {e}")
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        raise HTTPException(status_code=500, detail=str(e))

    if reservation_id:
        await _metering.commit_reservation(reservation_id)

    # 3. Update Result and Metadata
    # Update InMemory Jobs
    if req.clip_index < len(job['result']['clips']):
         job['result']['clips'][req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
    
    # Update Metadata on Disk (Persistence)
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
            # Update the main data structure
            data['shorts'] = clips
            
            # Write back
            save_metadata(json_files[0], data)
            print(f"✅ Metadata updated with subtitled video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")
        # Non-critical, but good for persistence

    _archive_clip_edit_bg(req.job_id, req.clip_index, output_filename)

    return {
        "success": True,
        "new_video_url": f"/videos/{req.job_id}/{output_filename}"
    }

class RemoveSubtitlesRequest(BaseModel):
    job_id: str
    clip_index: int
    input_filename: Optional[str] = None


@router.post("/api/subtitle/remove")
async def remove_subtitles(req: RemoveSubtitlesRequest, request: Request):
    """Point a clip back at its un-captioned original.

    Clips ship captioned by default now, so there has to be a way out — without
    this, a user who doesn't want captions is stuck with them. No re-encode and
    no quota: the pipeline always keeps the clean file next to the derived
    ``subtitled_<ts>_`` one, so removing is just choosing the other file.
    """
    await require_managed_entitlement(request)
    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[req.job_id]
    await _assert_job_owner(request, job)

    output_dir = os.path.join(state.OUTPUT_DIR, req.job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")
    data = load_metadata(json_files[0])
    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    filename = os.path.basename(
        req.input_filename
        or (clips[req.clip_index].get('video_url') or '').split('/')[-1]
        or f"{metadata_base_name(json_files[0])}"
           f"_clip_{req.clip_index + 1}.mp4")

    # Same walk-back the burn path uses, so this undoes any number of restyles.
    while True:
        m = re.match(r'^subtitled_\d+_(.+)$', filename)
        if not m or not os.path.exists(os.path.join(output_dir, m.group(1))):
            break
        filename = m.group(1)

    if not os.path.exists(os.path.join(output_dir, filename)):
        raise HTTPException(status_code=404,
                            detail="The original clip is no longer available.")

    new_url = f"/videos/{req.job_id}/{filename}"
    if req.clip_index < len(job.get('result', {}).get('clips', [])):
        job['result']['clips'][req.clip_index]['video_url'] = new_url
    try:
        clips[req.clip_index]['video_url'] = new_url
        data['shorts'] = clips
        save_metadata(json_files[0], data)
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")

    _archive_clip_edit_bg(req.job_id, req.clip_index, filename)
    return {"success": True, "new_video_url": new_url}


class HookRequest(BaseModel):
    job_id: str
    clip_index: int
    text: Optional[str] = ""
    input_filename: Optional[str] = None
    position: Optional[str] = "top" # top, center, bottom
    size: Optional[str] = "M" # S, M, L
    duration_seconds: Optional[float] = None  # None = hook visible for the whole clip
    style: Optional[str] = "classic"  # classic/dark/yellow/red/outline/outline_yellow
    remove: Optional[bool] = False  # strip the burned hook instead of adding one

@router.post("/api/hook")
async def add_hook(req: HookRequest, request: Request):
    await require_managed_entitlement(request)
    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[req.job_id]
    await _assert_job_owner(request, job)
    output_dir = os.path.join(state.OUTPUT_DIR, req.job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))

    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")

    data = load_metadata(json_files[0])
    
    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")
        
    clip_data = clips[req.clip_index]
    
    # Video Path
    if req.input_filename:
        filename = os.path.basename(req.input_filename)
    else:
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = metadata_base_name(json_files[0])
             filename = f"{base_name}_clip_{req.clip_index+1}.mp4"
         
    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    if not req.remove and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Hook text is required")

    # Same invariant as /api/edit: derive from the clip WITHOUT its burned
    # captions, then put them back on top, so a later restyle never stacks a
    # second caption layer (see _reapply_captions). The hook layer is stripped
    # too: a new hook REPLACES the burned one (auto-hook or a previous manual
    # one) instead of stacking on top of it.
    clean_name = _strip_burned_captions(output_dir, filename)
    had_captions = clean_name != filename
    clean_name = _strip_burned_hook(output_dir, clean_name)
    filename = clean_name
    input_path = os.path.join(output_dir, clean_name)

    if req.remove:
        # Nothing to burn: the hook-less file is the target; captions (if the
        # clip had them) go back on below.
        output_filename = filename
        output_path = input_path
        reservation_id = None
    else:
        output_filename = f"hooked_{int(time.time())}_{filename}"
        output_path = os.path.join(output_dir, output_filename)

        # Map Size to Scale
        size_map = {"S": 0.8, "M": 1.0, "L": 1.3}
        font_scale = size_map.get(req.size, 1.0)

        # Meter the FFmpeg overlay re-encode (no-op for BYOK / self-host).
        hook_minutes = _cloud_config.HOOK_MINUTES if state.BILLING_ENABLED else 0
        reservation_id = await reserve_managed_action(
            request, hook_minutes, req.job_id, "hook")

        try:
            # Run in thread pool
            def run_hook():
                add_hook_to_video(input_path, req.text, output_path, position=req.position, font_scale=font_scale, duration=req.duration_seconds, style=req.style)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_hook)

        except Exception as e:
            print(f"❌ Hook Error: {e}")
            if reservation_id:
                await _metering.release_reservation(reservation_id)
            raise HTTPException(status_code=500, detail=str(e))

        if reservation_id:
            await _metering.commit_reservation(reservation_id)

    # Captions back on top (see /api/edit for the same invariant).
    if had_captions:
        recap = await asyncio.get_event_loop().run_in_executor(
            None, _reapply_captions, req.job_id, req.clip_index, output_path)
        if recap:
            output_filename = os.path.basename(recap)

    # Record the burned hook so the editor knows what the clip carries (the
    # auto-hook pipeline writes the same key).
    if req.remove:
        clip_data.pop('auto_hook', None)
    else:
        clip_data['auto_hook'] = {
            "text": req.text, "style": req.style, "position": req.position,
            "duration_seconds": req.duration_seconds,
        }

    # Update Persistence (Same logic as subtitles)
    # Update InMemory Jobs
    if req.clip_index < len(job['result']['clips']):
        mem_clip = job['result']['clips'][req.clip_index]
        mem_clip['video_url'] = f"/videos/{req.job_id}/{output_filename}"
        if req.remove:
            mem_clip.pop('auto_hook', None)
        else:
            mem_clip['auto_hook'] = clip_data['auto_hook']

    # Update Metadata on Disk
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
            data['shorts'] = clips
            save_metadata(json_files[0], data)
            print(f"✅ Metadata updated with hook video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")

    _archive_clip_edit_bg(req.job_id, req.clip_index, output_filename)

    return {
        "success": True,
        "new_video_url": f"/videos/{req.job_id}/{output_filename}",
        "burned_hook": None if req.remove else clip_data['auto_hook'],
    }

class TranslateRequest(BaseModel):
    job_id: str
    clip_index: int
    target_language: str
    source_language: Optional[str] = None
    input_filename: Optional[str] = None

@router.get("/api/translate/languages")
async def get_languages():
    """Return supported languages for translation."""
    return {"languages": get_supported_languages()}

@router.post("/api/translate")
async def translate_clip(
    req: TranslateRequest,
    request: Request,
    x_elevenlabs_key: Optional[str] = Header(None, alias="X-ElevenLabs-Key")
):
    """Translate a video clip to a different language using ElevenLabs dubbing."""
    if not x_elevenlabs_key:
        raise HTTPException(status_code=400, detail="Missing X-ElevenLabs-Key header")

    await _ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[req.job_id]
    await _assert_job_owner(request, job)
    output_dir = os.path.join(state.OUTPUT_DIR, req.job_id)
    json_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))

    if not json_files:
        raise HTTPException(status_code=404, detail="Metadata not found")

    data = load_metadata(json_files[0])

    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail="Clip not found")

    clip_data = clips[req.clip_index]

    # Video Path
    if req.input_filename:
        filename = os.path.basename(req.input_filename)
    else:
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
             base_name = metadata_base_name(json_files[0])
             filename = f"{base_name}_clip_{req.clip_index+1}.mp4"

    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    # Output video with language suffix
    base, ext = os.path.splitext(filename)
    output_filename = f"translated_{req.target_language}_{base}{ext}"
    output_path = os.path.join(output_dir, output_filename)

    try:
        # Run translation in thread pool (blocking API calls)
        def run_translate():
            return translate_video(
                video_path=input_path,
                output_path=output_path,
                target_language=req.target_language,
                api_key=x_elevenlabs_key,
                source_language=req.source_language,
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_translate)

    except Exception as e:
        print(f"❌ Translation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Update InMemory Jobs
    if req.clip_index < len(job['result']['clips']):
         job['result']['clips'][req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"

    # Update Metadata on Disk
    try:
        if req.clip_index < len(clips):
            clips[req.clip_index]['video_url'] = f"/videos/{req.job_id}/{output_filename}"
            data['shorts'] = clips
            save_metadata(json_files[0], data)
            print(f"✅ Metadata updated with translated video for clip {req.clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")

    _archive_clip_edit_bg(req.job_id, req.clip_index, output_filename)

    return {
        "success": True,
        "new_video_url": f"/videos/{req.job_id}/{output_filename}"
    }
