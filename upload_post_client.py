"""Upload-Post vendor client: one home for the API surface.

The social routes, the Thumbnail Studio publish, and the parked SaaSShorts
poster each used to hand-build the same URLs and Authorization header —
nine inline literals across server/routes/. The vendor API lives at one
base, so its address lives in one module (same pattern as s3_uploader.py).
"""
import httpx

API_BASE = "https://api.upload-post.com/api"

UPLOAD_URL = f"{API_BASE}/upload"
USERS_URL = f"{API_BASE}/uploadposts/users"
POST_ANALYTICS_CACHED_URL = f"{API_BASE}/uploadposts/post-analytics/cached"
SCHEDULE_URL = f"{API_BASE}/uploadposts/schedule"


def profile_analytics_url(profile: str) -> str:
    return f"{API_BASE}/analytics/{profile}"


def auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Apikey {api_key}"}


def upload_multipart(api_key: str, data: dict, files: dict, timeout: float = 120.0) -> httpx.Response:
    """The video+multipart POST every posting path uses. Synchronous client:
    the async one chokes on multipart file payloads (see the social route)."""
    with httpx.Client(timeout=timeout) as client:
        return client.post(UPLOAD_URL, headers=auth_headers(api_key),
                           data=data, files=files)
