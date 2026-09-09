"""Social distribution routes: posting, profiles, analytics, scheduling.

Everything Upload-Post-shaped lives here. Shared request helpers
(`resolve_upload_post`, `resolve_post_profile`, `_assert_job_owner`,
`_ensure_job_files`, `_user_from_request`) still live in app.py until the
job-core split (T6c) moves them to deps.py — reaching them through `_app`
at *call* time keeps this seam cycle-free at *import* time (app.py imports
this module while itself partially initialized; attribute lookup happens per
request, when app is complete). Interface: `router` only.
"""

import os
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import BILLING_ENABLED, OUTPUT_DIR, TIKTOK_POST_MODE
from state import jobs

router = APIRouter()


def _app():
    """App-owned shared helpers (`resolve_upload_post`, `_assert_job_owner`, …).

    Imported lazily (per call, then cached by sys.modules) so this module is
    importable on its own: a module-top `import app` made `import
    routers.social` order-dependent (app includes this router while itself
    partially initialized). T6c moves these helpers to deps.py and this shim
    goes away."""
    import app
    return app


class SocialPostRequest(BaseModel):
    job_id: str
    clip_index: int
    api_key: Optional[str] = None  # BYOK; ignored for managed users
    user_id: Optional[str] = None  # BYOK profile; ignored for managed users
    platforms: List[str]  # ["tiktok", "instagram", "youtube"]
    # Optional overrides if frontend wants to edit them
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None  # ISO-8601 string
    timezone: Optional[str] = "UTC"


@router.post("/api/social/post")
async def post_to_socials(req: SocialPostRequest, request: Request):
    await _app()._ensure_job_files(req.job_id, request)
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    # Resolve the Upload-Post key + profile. For managed users the server key is
    # used and their own profile is forced (body api_key / user_id are ignored).
    upload_key, forced_profile = await _app().resolve_upload_post(request, req.api_key)
    if not upload_key:
        raise HTTPException(status_code=400, detail="Missing Upload-Post API key")
    post_user = _app().resolve_post_profile(forced_profile, req.user_id)

    job = jobs[req.job_id]
    await _app()._assert_job_owner(request, job)
    if 'result' not in job or 'clips' not in job['result']:
        raise HTTPException(status_code=400, detail="Job result not available")

    try:
        clip = job['result']['clips'][req.clip_index]
        # Video URL is relative /videos/..., we need absolute file path
        # clip['video_url'] is like "/videos/{job_id}/{filename}"
        # We constructed it as: f"/videos/{job_id}/{clip_filename}"
        # And file is at f"{OUTPUT_DIR}/{job_id}/{clip_filename}"

        filename = clip['video_url'].split('/')[-1]
        file_path = os.path.join(OUTPUT_DIR, req.job_id, filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Video file not found: {file_path}")

        # Construct parameters for Upload-Post API
        # Fallbacks
        final_title = req.title or clip.get('title', 'Viral Short')
        final_description = req.description or clip.get('video_description_for_instagram') or clip.get('video_description_for_tiktok') or "Check this out!"

        # Prepare form data
        url = "https://api.upload-post.com/api/upload"
        headers = {
            "Authorization": f"Apikey {upload_key}"
        }

        # Prepare data as dict (httpx handles lists for multiple values)
        data_payload = {
            "user": post_user,
            "title": final_title,
            "platform[]": req.platforms,  # Pass list directly
            "async_upload": "true"  # Enable async upload
        }

        # Add scheduling if present
        if req.scheduled_date:
            data_payload["scheduled_date"] = req.scheduled_date
            if req.timezone:
                data_payload["timezone"] = req.timezone

        # Add Platform specifics
        if "tiktok" in req.platforms:
            data_payload["tiktok_title"] = final_description
            data_payload["post_mode"] = TIKTOK_POST_MODE

        if "instagram" in req.platforms:
            data_payload["instagram_title"] = final_description
            data_payload["media_type"] = "REELS"

        if "youtube" in req.platforms:
            yt_title = req.title or clip.get('video_title_for_youtube_short', final_title)
            data_payload["youtube_title"] = yt_title
            data_payload["youtube_description"] = final_description
            data_payload["privacyStatus"] = "public"

        # Send File
        # httpx AsyncClient requires async file reading or bytes.
        # Since we have MAX_FILE_SIZE_MB, reading into memory is safe-ish.
        with open(file_path, "rb") as f:
            file_content = f.read()

        files = {
            "video": (filename, file_content, "video/mp4")
        }

        # Switch to synchronous Client to avoid "sync request with AsyncClient" error with multipart/files
        with httpx.Client(timeout=120.0) as client:
            print(f"📡 Sending to Upload-Post for platforms: {req.platforms}")
            response = client.post(url, headers=headers, data=data_payload, files=files)

        if response.status_code not in [200, 201, 202]:  # Added 201
            print(f"❌ Upload-Post Error: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Vendor API Error: {response.text}")

        return response.json()

    except Exception as e:
        print(f"❌ Social Post Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/social/user")
async def get_social_user(request: Request):
    """Proxy to fetch user profiles from Upload-Post.

    BYOK: uses the caller's key and returns all profiles on that account.
    Managed: uses the server key but returns ONLY the caller's own profile.
    """
    api_key, forced_profile = await _app().resolve_upload_post(request, None)
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing X-Upload-Post-Key header")

    url = "https://api.upload-post.com/api/uploadposts/users"
    print(f"🔍 Fetching User ID from: {url}")
    headers = {"Authorization": f"Apikey {api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"❌ Upload-Post User Fetch Error: {resp.text}")
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch user: {resp.text}")

            data = resp.json()
            print(f"🔍 Upload-Post User Response: {data}")

            # The structure is {'success': True, 'profiles': [{'username': '...'}, ...]}
            profiles_list = []
            if isinstance(data, dict):
                raw_profiles = data.get('profiles', [])
                if isinstance(raw_profiles, list):
                    for p in raw_profiles:
                        username = p.get('username')
                        if username:
                            # Determine connected platforms
                            socials = p.get('social_accounts', {})
                            connected = []
                            # Check typical platforms
                            for platform in ['tiktok', 'instagram', 'youtube']:
                                account_info = socials.get(platform)
                                # If it's a dict and typically has data, or just not empty string
                                if isinstance(account_info, dict):
                                    connected.append(platform)

                            profiles_list.append({
                                "username": username,
                                "connected": connected
                            })

            # Managed users must only ever see their own profile.
            if forced_profile is not None:
                profiles_list = [p for p in profiles_list if p.get("username") == forced_profile]

            if not profiles_list:
                # Fallback if no profiles found
                return {"profiles": [], "error": "No profiles found"}

            return {"profiles": profiles_list}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# --- Social analytics (thin proxies over Upload-Post) ---
# Read-only mirrors of the posting flow above: managed users are locked to their
# own profile (the body/query profile is ignored), BYOK callers bring their own
# key and pick the profile with ?user=.

# Separate bucket from _probe_times: analytics polling must not eat into the
# metering-probe allowance, and vice versa. Protects the managed Upload-Post
# key's vendor rate limits from a runaway polling loop.
_analytics_times: dict = {}  # user_id -> [monotonic timestamps]
ANALYTICS_PER_HOUR = 60


def _check_analytics_rate(user_id):
    now = time.monotonic()
    times = _analytics_times.setdefault(str(user_id), [])
    times[:] = [t for t in times if now - t < 3600]
    if len(times) >= ANALYTICS_PER_HOUR:
        raise HTTPException(status_code=429,
                            detail="Too many analytics requests this hour. Please slow down.")
    times.append(now)


async def _social_analytics_auth(request: Request, byok_profile: Optional[str]):
    api_key, forced_profile = await _app().resolve_upload_post(request, None)
    if not api_key:
        if BILLING_ENABLED:
            # Signed-in free user (or no auth at all): social posting is
            # paid-only in cloud, so there are no posts to measure either.
            raise HTTPException(status_code=402, detail={
                "error": "no_plan",
                "message": "Social analytics needs an active plan.",
            })
        raise HTTPException(status_code=400, detail="Missing X-Upload-Post-Key header")
    if forced_profile:
        user = await _app()._user_from_request(request)
        if user:
            _check_analytics_rate(user.id)
    return api_key, _app().resolve_post_profile(forced_profile, byok_profile)


async def _upload_post_get(api_key: str, url: str, params: dict):
    headers = {"Authorization": f"Apikey {api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Vendor API Error: {resp.text}")
    return resp.json()


@router.get("/api/social/analytics")
async def social_profile_analytics(
    request: Request,
    platforms: str = "tiktok,instagram,youtube",
    user: Optional[str] = None,
):
    """Aggregated profile analytics: followers, views, engagement per platform."""
    api_key, profile = await _social_analytics_auth(request, user)
    return await _upload_post_get(
        api_key,
        f"https://api.upload-post.com/api/analytics/{profile}",
        {"platforms": platforms},
    )


@router.get("/api/social/analytics/posts")
async def social_post_analytics(
    request: Request,
    platform: Optional[str] = None,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    user: Optional[str] = None,
):
    """Per-post metrics for the profile's published posts (Upload-Post cache)."""
    api_key, profile = await _social_analytics_auth(request, user)
    params = {"user": profile}
    for key, value in (("platform", platform), ("limit", limit),
                       ("cursor", cursor), ("since", since), ("until", until)):
        if value is not None:
            params[key] = value
    return await _upload_post_get(
        api_key,
        "https://api.upload-post.com/api/uploadposts/post-analytics/cached",
        params,
    )


_PERIOD_DAYS = {"last_day": 1, "last_week": 7, "last_month": 30,
                "last_3months": 90, "last_year": 365}


def _post_row_views(row: dict) -> float:
    metrics = row.get("post_metrics") or row.get("metrics") or row
    for key in ("views", "impressions", "plays"):
        value = metrics.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


@router.get("/api/social/analytics/impressions")
async def social_total_impressions(
    request: Request,
    period: Optional[str] = None,     # last_day | last_week | last_month | last_3months | last_year
    start_date: Optional[str] = None,  # YYYY-MM-DD
    end_date: Optional[str] = None,
    platform: Optional[str] = None,
    breakdown: Optional[bool] = None,
    user: Optional[str] = None,
):
    """Total impressions for the profile over a window.

    Computed by aggregating the profile-scoped post cache instead of proxying
    Upload-Post's /total-impressions: that endpoint echoes the requested
    profile but returns account-wide numbers (observed 2026-08-21 — a profile
    with zero posts got 85K Instagram impressions), which for managed users
    would leak other tenants' aggregates. The cache endpoint IS scoped by
    ?user=, so summing it is both correct and cheap.
    """
    api_key, profile = await _social_analytics_auth(request, user)

    days = _PERIOD_DAYS.get(period or "", 30)
    since = start_date or (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {"user": profile, "since": since, "limit": 200}
    if end_date:
        params["until"] = end_date
    if platform:
        params["platform"] = platform

    total = 0.0
    per_platform: dict = {}
    for _page in range(5):  # 1000 posts is far beyond any real profile window
        data = await _upload_post_get(
            api_key,
            "https://api.upload-post.com/api/uploadposts/post-analytics/cached",
            params,
        )
        rows = data.get("posts") or data.get("data") or data.get("items") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            views = _post_row_views(row)
            total += views
            name = row.get("platform")
            if name:
                per_platform[name] = per_platform.get(name, 0) + views
        cursor = data.get("next_cursor")
        if not cursor or not data.get("has_more"):
            break
        params["cursor"] = cursor

    result = {
        "profile_username": profile,
        "total_impressions": round(total),
        "per_platform": {k: round(v) for k, v in per_platform.items()},
    }
    return result


async def _scheduled_posts_for(api_key: str, profile: str) -> list:
    """The caller's pending scheduled posts.

    Upload-Post's GET /uploadposts/schedule takes no profile filter and returns
    everything the *account* has pending — with the managed key that is every
    OpenShorts user's queue, so the filter below is what keeps one tenant from
    seeing (or cancelling) another's. Same class of bug as the impressions
    endpoint; do not "simplify" it away.
    """
    data = await _upload_post_get(
        api_key, "https://api.upload-post.com/api/uploadposts/schedule", {})
    rows = data.get("scheduled_posts") or data.get("data") or []
    return [r for r in rows
            if isinstance(r, dict) and r.get("profile_username") == profile]


@router.get("/api/social/scheduled")
async def social_scheduled(request: Request, user: Optional[str] = None):
    """Pending scheduled posts for the caller's profile, soonest first."""
    api_key, profile = await _social_analytics_auth(request, user)
    rows = await _scheduled_posts_for(api_key, profile)
    rows.sort(key=lambda r: r.get("scheduled_date") or "")
    return {"profile_username": profile, "scheduled_posts": rows}


@router.delete("/api/social/scheduled/{job_id}")
async def social_cancel_scheduled(job_id: str, request: Request, user: Optional[str] = None):
    """Cancel one pending scheduled post, if it belongs to the caller."""
    api_key, profile = await _social_analytics_auth(request, user)
    rows = await _scheduled_posts_for(api_key, profile)
    if not any(r.get("job_id") == job_id for r in rows):
        # 404 rather than 403: never confirm that someone else's job exists.
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    headers = {"Authorization": f"Apikey {api_key}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"https://api.upload-post.com/api/uploadposts/schedule/{job_id}",
            headers=headers)
    if resp.status_code not in (200, 202, 204):
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Vendor API Error: {resp.text}")
    return {"success": True, "job_id": job_id}
