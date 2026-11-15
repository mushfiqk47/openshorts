"""Thumbnail Studio: upload + background-transcribe session, title
suggestions, thumbnail generation, YouTube description, and publish."""
import os
import json
import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel

from thumbnail import analyze_video_for_titles, refine_titles, generate_thumbnail, generate_youtube_description
import httpx

from server import state
from server.state import (
    thumbnail_sessions,
    publish_jobs,
    THUMBNAILS_DIR,
    _max_file_size_mb,
    _safe_under,
    cloud,
    managed_keys,
    _metering,
    _cloud_config,
)
from server.billing import (
    resolve_gemini,
    gemini_missing_error,
    resolve_upload_post,
    reserve_managed_action,
    require_managed_entitlement,
    _owner_id,
    _assert_job_owner,
)

router = APIRouter()

# --- Thumbnail Studio Endpoints ---

@router.post("/api/thumbnail/upload")
async def thumbnail_upload(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    """Upload video and start background transcription immediately."""
    await require_managed_entitlement(request)
    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    session_id = str(uuid.uuid4())
    transcript_event = asyncio.Event()

    # Save file if uploaded directly. basename() stops a "../../x" filename from
    # escaping state.UPLOAD_DIR; the chunked read caps memory so a huge body can't OOM.
    video_path = None
    if file:
        safe_name = os.path.basename(file.filename or "upload") or "upload"
        video_path = os.path.join(state.UPLOAD_DIR, f"thumb_{session_id}_{safe_name}")
        size = 0
        limit_bytes = _max_file_size_mb() * 1024 * 1024
        with open(video_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit_bytes:
                    os.remove(video_path)
                    raise HTTPException(status_code=413, detail=f"File too large. Max size {_max_file_size_mb()}MB")
                buffer.write(chunk)

    # Meter a fixed guard cost for the background download + transcription
    # so an entitled user can't loop it for free. Settled when the job finishes.
    transcribe_minutes = _cloud_config.TRANSCRIBE_MINUTES if state.BILLING_ENABLED else 0
    reservation_id = await reserve_managed_action(
        request, transcribe_minutes, session_id, "thumbnail_transcribe")

    # Initialize session
    thumbnail_sessions[session_id] = {
        "user_id": await _owner_id(request),
        "video_path": video_path,
        "transcript_event": transcript_event,
        "transcript_ready": False,
        "transcript": None,
        "transcript_segments": [],
        "video_duration": 0,
        "language": "en",
        "context": "",
        "titles": [],
        "conversation": [],
        "_url": url,  # Store URL for deferred download
    }

    async def run_background_transcribe():
        try:
            vpath = video_path
            # Download YouTube video if URL was provided
            if not vpath and url:
                from main import download_youtube_video
                loop = asyncio.get_event_loop()
                vpath, _ = await loop.run_in_executor(None, download_youtube_video, url, state.UPLOAD_DIR)
                thumbnail_sessions[session_id]["video_path"] = vpath

            from main import transcribe_video
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, transcribe_video, vpath)
            segments = transcript.get("segments", [])
            duration = segments[-1]["end"] if segments else 0

            thumbnail_sessions[session_id].update({
                "transcript_ready": True,
                "transcript": transcript,
                "transcript_segments": segments,
                "video_duration": duration,
                "language": transcript.get("language", "en"),
            })
            print(f"✅ [Thumbnail] Background transcription complete for session {session_id}")
            if reservation_id:
                await _metering.commit_reservation(reservation_id)
        except Exception as e:
            print(f"❌ [Thumbnail] Background transcription failed: {e}")
            thumbnail_sessions[session_id]["transcript_error"] = str(e)
            if reservation_id:
                await _metering.release_reservation(reservation_id)
        finally:
            transcript_event.set()

    asyncio.create_task(run_background_transcribe())

    return {"session_id": session_id}


@router.post("/api/thumbnail/analyze")
async def thumbnail_analyze(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """Analyze a video and suggest viral YouTube titles."""
    api_key = await resolve_gemini(request)
    if not api_key:
        raise gemini_missing_error()

    pre_transcript = None

    # Check for pre-existing session with background transcription
    if session_id and session_id in thumbnail_sessions:
        session = thumbnail_sessions[session_id]
        await _assert_job_owner(request, session)

        # Wait for background transcription to complete
        transcript_event = session.get("transcript_event")
        if transcript_event:
            print(f"⏳ [Thumbnail] Waiting for background transcription to finish...")
            await transcript_event.wait()

        if session.get("transcript_error"):
            raise HTTPException(status_code=500, detail=f"Transcription failed: {session['transcript_error']}")

        video_path = session["video_path"]
        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found in session")

        if session.get("transcript_ready"):
            pre_transcript = session["transcript"]
    else:
        # No pre-existing session — need file or URL
        if not url and not file:
            raise HTTPException(status_code=400, detail="Must provide URL, File, or session_id")

        session_id = str(uuid.uuid4())

        if url:
            from main import download_youtube_video
            video_path, _ = download_youtube_video(url, state.UPLOAD_DIR)
        else:
            safe_name = os.path.basename(file.filename or "upload") or "upload"
            video_path = os.path.join(state.UPLOAD_DIR, f"thumb_{session_id}_{safe_name}")
            size = 0
            limit_bytes = _max_file_size_mb() * 1024 * 1024
            with open(video_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit_bytes:
                        os.remove(video_path)
                        raise HTTPException(status_code=413, detail=f"File too large. Max size {_max_file_size_mb()}MB")
                    buffer.write(chunk)

    # Meter the managed Gemini analysis (no-op for self-host).
    analyze_minutes = _cloud_config.MANAGED_ANALYSIS_MINUTES if state.BILLING_ENABLED else 0
    reservation_id = await reserve_managed_action(request, analyze_minutes, session_id, "thumbnail_analyze")

    try:
        # Run analysis in thread pool (skips ASR if pre_transcript is available)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, analyze_video_for_titles, api_key, video_path, pre_transcript)

        # Store/update session context
        if session_id not in thumbnail_sessions:
            thumbnail_sessions[session_id] = {"user_id": await _owner_id(request)}

        thumbnail_sessions[session_id].update({
            "context": result.get("transcript_summary", ""),
            "titles": result.get("titles", []),
            "language": result.get("language", "en"),
            "conversation": thumbnail_sessions[session_id].get("conversation", []),
            "video_path": video_path,
            "transcript_segments": result.get("segments", []),
            "video_duration": result.get("video_duration", 0)
        })

        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        return {
            "session_id": session_id,
            "titles": result.get("titles", []),
            "context": result.get("transcript_summary", ""),
            "language": result.get("language", "en"),
            "recommended": result.get("recommended", [])
        }

    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        print(f"❌ Thumbnail Analyze Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ThumbnailTitlesRequest(BaseModel):
    session_id: Optional[str] = None
    message: Optional[str] = None
    title: Optional[str] = None

@router.post("/api/thumbnail/titles")
async def thumbnail_titles(
    req: ThumbnailTitlesRequest,
    request: Request,
):
    """Refine title suggestions or accept a manual title."""
    api_key = await resolve_gemini(request)
    if not api_key:
        raise gemini_missing_error()

    # Manual title mode - just create a session with the user's title
    if req.title:
        session_id = req.session_id or str(uuid.uuid4())
        if session_id not in thumbnail_sessions:
            thumbnail_sessions[session_id] = {
                "user_id": await _owner_id(request),
                "context": "",
                "titles": [req.title],
                "language": "en",
                "conversation": []
            }
        else:
            await _assert_job_owner(request, thumbnail_sessions[session_id])
        return {"session_id": session_id, "titles": [req.title]}

    # Refinement mode
    if not req.session_id or req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    if not req.message:
        raise HTTPException(status_code=400, detail="Must provide message or title")

    session = thumbnail_sessions[req.session_id]
    await _assert_job_owner(request, session)

    # Add user message to conversation history
    session["conversation"].append({"role": "user", "content": req.message})

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            refine_titles,
            api_key,
            session["context"],
            req.message,
            session["conversation"]
        )

        new_titles = result.get("titles", [])
        session["titles"] = new_titles
        session["conversation"].append({"role": "assistant", "content": json.dumps(new_titles)})

        return {"titles": new_titles}

    except Exception as e:
        print(f"❌ Thumbnail Titles Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thumbnail/generate")
async def thumbnail_generate(
    request: Request,
    session_id: str = Form(...),
    title: str = Form(...),
    extra_prompt: str = Form(""),
    count: int = Form(3),
    face: Optional[UploadFile] = File(None),
    background: Optional[UploadFile] = File(None),
):
    """Generate YouTube thumbnails with Gemini image generation."""
    api_key = await resolve_gemini(request)
    if not api_key:
        raise gemini_missing_error()

    # Image generation is the one expensive managed Gemini call — paid plans only.
    if state.BILLING_ENABLED:
        user = await _user_from_request(request)
        if user is not None and user.plan == "free":
            raise HTTPException(status_code=403, detail={
                "error": "plan_required",
                "message": "AI thumbnail generation is available on paid plans.",
            })

    # Clamp count
    count = min(max(1, count), 6)

    # Gemini image generation is the expensive managed call — meter it against the
    # plan quota (a batch ≈ THUMBNAIL_MINUTES). No-op for BYOK / self-host.
    thumb_minutes = _cloud_config.THUMBNAIL_MINUTES if state.BILLING_ENABLED else 0
    reservation_id = await reserve_managed_action(request, thumb_minutes, session_id, "thumbnail")

    # Save optional uploaded images. basename() on the session id and filenames
    # keeps everything inside state.UPLOAD_DIR (no "../" escape from client input).
    face_path = None
    bg_path = None
    safe_session = os.path.basename(session_id) or "session"
    thumb_upload_dir = os.path.join(state.UPLOAD_DIR, f"thumb_{safe_session}")
    os.makedirs(thumb_upload_dir, exist_ok=True)

    try:
        if face and face.filename:
            face_name = os.path.basename(face.filename)
            face_path = os.path.join(thumb_upload_dir, f"face_{face_name}")
            with open(face_path, "wb") as f:
                f.write(await face.read())

        if background and background.filename:
            bg_name = os.path.basename(background.filename)
            bg_path = os.path.join(thumb_upload_dir, f"bg_{bg_name}")
            with open(bg_path, "wb") as f:
                f.write(await background.read())

        # Get video context from session (transcript summary from analysis step)
        video_context = ""
        if session_id in thumbnail_sessions:
            video_context = thumbnail_sessions[session_id].get("context", "")

        # Run generation in thread pool
        loop = asyncio.get_event_loop()
        thumbnails = await loop.run_in_executor(
            None,
            generate_thumbnail,
            api_key,
            title,
            session_id,
            face_path,
            bg_path,
            extra_prompt,
            count,
            video_context
        )

        if not thumbnails:
            raise HTTPException(status_code=500, detail="Thumbnail generation failed. Please check your Gemini API key has access to image generation (gemini-3.1-flash-image-preview model).")

        # Success — charge the reserved minutes.
        if reservation_id:
            await _metering.commit_reservation(reservation_id)
        return {"thumbnails": thumbnails}

    except HTTPException:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        raise
    except Exception as e:
        if reservation_id:
            await _metering.release_reservation(reservation_id)
        print(f"❌ Thumbnail Generate Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ThumbnailDescribeRequest(BaseModel):
    session_id: str
    title: str

@router.post("/api/thumbnail/describe")
async def thumbnail_describe(
    req: ThumbnailDescribeRequest,
    request: Request,
):
    """Generate a YouTube description with chapters from the transcript."""
    api_key = await resolve_gemini(request)
    if not api_key:
        raise gemini_missing_error()

    if req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = thumbnail_sessions[req.session_id]
    await _assert_job_owner(request, session)
    segments = session.get("transcript_segments", [])
    if not segments:
        raise HTTPException(status_code=400, detail="No transcript segments available. Please analyze a video first.")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            generate_youtube_description,
            api_key,
            req.title,
            segments,
            session.get("language", "en"),
            session.get("video_duration", 0)
        )
        return {"description": result.get("description", "")}

    except Exception as e:
        print(f"❌ Thumbnail Describe Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/thumbnail/publish")
async def thumbnail_publish(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    thumbnail_url: str = Form(...),
    api_key: Optional[str] = Form(None),   # BYOK; ignored for managed users
    user_id: Optional[str] = Form(None),   # BYOK profile; ignored for managed users
):
    """Kick off a background upload to YouTube via Upload-Post and return immediately."""
    if session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Managed users: server key + forced own profile; body fields ignored.
    upload_key, forced_profile = await resolve_upload_post(request, api_key)
    if not upload_key:
        raise HTTPException(status_code=400, detail="Missing Upload-Post API key")
    post_user = forced_profile or user_id
    if not post_user:
        raise HTTPException(status_code=400, detail="Missing Upload-Post user profile")

    session = thumbnail_sessions[session_id]
    await _assert_job_owner(request, session)
    video_path = session.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Original video file not found")

    # Resolve thumbnail path from URL — sanitize against path traversal so a
    # crafted thumbnail_url (e.g. "thumbnails/../../.env") can't read server
    # files and exfiltrate them via the Upload-Post multipart body.
    thumb_relative = thumbnail_url.lstrip("/")
    if thumb_relative.startswith("thumbnails/"):
        thumb_path = _safe_under(state.OUTPUT_DIR, thumb_relative)
    else:
        thumb_path = _safe_under(THUMBNAILS_DIR, thumb_relative)

    if not thumb_path:
        raise HTTPException(status_code=400, detail="Invalid thumbnail path")
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="Thumbnail file not found")

    # Generate a unique ID for this publish job so the frontend can poll
    publish_id = str(uuid.uuid4())
    publish_jobs[publish_id] = {"status": "uploading", "result": None, "error": None}

    def do_upload():
        """Runs in a thread via BackgroundTasks — does the actual multipart upload."""
        try:
            upload_url = "https://api.upload-post.com/api/upload"
            headers = {"Authorization": f"Apikey {upload_key}"}
            data_payload = {
                "user": post_user,
                "platform[]": ["youtube"],
                "title": title,          # required base field (fallback)
                "async_upload": "true",
                "youtube_title": title,
                "youtube_description": description,
                "privacyStatus": "public",
            }
            video_filename = os.path.basename(video_path)
            thumb_filename = os.path.basename(thumb_path)

            print(f"📡 [Thumbnail] Publishing to YouTube via Upload-Post... (publish_id={publish_id})")
            with open(video_path, "rb") as vf, open(thumb_path, "rb") as tf:
                files = {
                    "video": (video_filename, vf.read(), "video/mp4"),
                    "thumbnail": (thumb_filename, tf.read(), "image/jpeg"),
                }

            # Use a long timeout — video uploads can take several minutes
            with httpx.Client(timeout=600.0) as client:
                response = client.post(upload_url, headers=headers, data=data_payload, files=files)

            if response.status_code not in [200, 201, 202]:
                err = f"Upload-Post API Error ({response.status_code}): {response.text}"
                print(f"❌ {err}")
                publish_jobs[publish_id]["status"] = "failed"
                publish_jobs[publish_id]["error"] = err
            else:
                print(f"✅ [Thumbnail] Published successfully (publish_id={publish_id})")
                publish_jobs[publish_id]["status"] = "done"
                publish_jobs[publish_id]["result"] = response.json()

        except Exception as e:
            err = str(e)
            print(f"❌ Thumbnail Publish Background Error: {err}")
            publish_jobs[publish_id]["status"] = "failed"
            publish_jobs[publish_id]["error"] = err

    background_tasks.add_task(do_upload)
    return {"publish_id": publish_id, "status": "uploading"}


@router.get("/api/thumbnail/publish/status/{publish_id}")
async def thumbnail_publish_status(publish_id: str):
    """Poll the status of a background publish job."""
    if publish_id not in publish_jobs:
        raise HTTPException(status_code=404, detail="Publish job not found")
    return publish_jobs[publish_id]
