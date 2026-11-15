"""ASGI entrypoint (``uvicorn app:app``): assembles the FastAPI application
from the server/ package. Route families live in server/routes/*, the job
engine in server/jobs.py, shared state in server/state.py."""
import os
import sys
import asyncio
from contextlib import asynccontextmanager

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server import state
from server.state import cloud, _alerts
from server.jobs import (
    _recover_jobs_from_disk,
    _resume_interrupted_jobs,
    process_queue,
    cleanup_jobs,
)
from server.routes import system, process, clips, captions, social, thumbnails

# Back-compat re-exports: tests and tooling reach these through ``app``.
# Anything tests REASSIGN must be patched on server.state / the owning module
# instead (re-export bindings here are read-only).
from server.state import (  # noqa: F401
    jobs,
    concurrency_semaphore,
    MAX_CONCURRENT_JOBS,
    _concurrency_capacity,
    _max_file_size_mb,
    _refresh_concurrency_semaphore,
)
from server.jobs import (  # noqa: F401
    _job_error_text,
    _sign_webhook,
    _strip_burned_captions,
    _strip_burned_hook,
    _canonical_clip_file,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Rehydrate finished jobs from disk before serving (survives restarts).
    _recover_jobs_from_disk()
    # Re-enqueue jobs that were mid-processing when we stopped (redeploy). Their
    # reservations must survive the orphan sweep so the resumed run can settle them.
    _resumed_reservation_ids = _resume_interrupted_jobs()
    # Start worker and cleanup
    worker_task = asyncio.create_task(process_queue())
    cleanup_task = asyncio.create_task(cleanup_jobs())
    if state.BILLING_ENABLED:
        await cloud.setup_async(app, keep_reservation_ids=_resumed_reservation_ids)
        # Nag on Telegram while the residential proxy is down/out of credits —
        # a single job-failure alert is easy to miss and ingest stays broken
        # until someone tops the balance up.
        asyncio.create_task(_alerts.proxy_watch_loop())
    yield
    # Cleanup (optional: cancel worker)


app = FastAPI(lifespan=lifespan)

# Cloud mode: attach middleware + routers at import time (before the app serves).
if state.BILLING_ENABLED:
    cloud.setup_sync(app)

# MCP server (/mcp): the pipeline as agent-callable tools. Works in both modes —
# cloud requires an osk_ API key, self-host keeps BYOK (see mcp_server.py).
import mcp_server as _mcp_server  # noqa: E402
app.include_router(_mcp_server.router)

# Enable CORS for frontend. Cloud mode locks this down to the configured origins;
# self-host keeps the permissive wildcard it has always used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cloud.settings.allowed_origins if state.BILLING_ENABLED else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving videos
app.mount("/videos", StaticFiles(directory=state.OUTPUT_DIR), name="videos")

# Mount static files for serving thumbnails
app.mount("/thumbnails", StaticFiles(directory=state.THUMBNAILS_DIR), name="thumbnails")

# ---- Route families ----------------------------------------------------------
app.include_router(system.router)
app.include_router(process.router)
app.include_router(clips.router)
app.include_router(captions.router)
app.include_router(social.router)
app.include_router(thumbnails.router)

# SaaSShorts (AI UGC generator) is parked: the dashboard tabs that drove it
# were removed, so it only mounts when explicitly re-enabled.
if state.SAASSHORTS_ENABLED:
    from server.routes.saasshorts import router as saasshorts_router

    app.include_router(saasshorts_router)
