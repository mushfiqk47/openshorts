# Architecture — OpenShorts

Living map of the codebase in **codebase-design** terms: every entry names its
**Module**, its **Interface** (everything a caller must know), the **Seam**
where that interface lives, and the **Depth** (behaviour per unit of interface).
A module earns its keep when deleting it pushes complexity back onto N callers
(the deletion test). One adapter = hypothetical seam; two adapters = real seam.

## Backend (Python / FastAPI)

| Module | Interface | Seam | Depth |
|---|---|---|---|
| `app.py` — HTTP tier + job queue | REST routes, `app` object | `app:app` (uvicorn entry) | DEEPENED: 4,327 → 3,616 lines. Composition root + job-core routes; split clusters live in `routers/`. |
| `config.py` ✨ NEW | env-derived constants, `layout_env()` | `config` module | DEEP: single bottom-of-stack Module; values freeze at import (conftest sets env first). |
| `state.py` ✨ NEW | `jobs`, `publish_jobs`, `job_queue`, `_enqueue_job` | `state` module | DEEP: identical objects — `app_module.jobs` mutation by tests still passes. |
| `routers/` ✨ NEW (`system`, `gallery`, `social`) | one `router` per module | `app.include_router(...)` (same idiom as `mcp_server.router`) | DEEP: 16 routes moved, AST-proven equivalent; social reaches app-owned helpers via call-time `_app` until T6c. |
| `pipeline/tracking.py` ✨ NEW | `SmoothedCameraman`, `SpeakerTracker` | `pipeline.tracking` | DEEP: numpy-only import, no ML stack needed. |
| `main.py` — clip pipeline | `python main.py -i …` CLI + `run_job()` called from `app.py` | function args / job dict | DEEPENING: 1,864 → 1,606 lines (tracking extracted to `pipeline/`). Download → scenes → Gemini → ffmpeg → reframe; T8b stages remain. |
| `reframe_v2.py` | `reframe_clip(src, dst, …)` | function signature | DEEP: one call hides TRACK/GENERAL/WIDE routing. Good shape, keep. |
| `split_layout.py` / `screencast_layout.py` / `camera_inset.py` | `apply(…)` each; chosen by `layout_picker.py` | `layout_picker.apply()` — the ONLY place layouts are decided | DEEP: picker is one Gemini call per source video; layouts only ADD, never override an explicit user choice. Do not re-ask Gemini per clip. |
| `active_speaker.py` / `punch_in.py` | trajectory / beat modifiers on the TRACK path | TRACK crop command (`x` → `w/h/x/y`) | DEEP internal seams; callers see plain TRACK. |
| `editor.py` / `edit_builder.py` | FFmpeg filter generation from Gemini JSON | `/api/edit` body | Medium: filter strings leak FFmpeg detail to callers — acceptable, filters ARE the product. |
| `subtitles.py` / `hooks.py` / `translate.py` | `POST /api/subtitle`, `/api/hook`, `/api/translate` | REST + `srt` files | DEEP enough; dubbed videos auto-retranscribe (keep). |
| `llm_client.py` / `openrouter_client.py` / `gemini_worker.py` | `complete(prompt, …)` | provider env (`layout_env`) | One real seam (two adapters: Gemini ↔ OpenRouter). Justifies the abstraction. |
| `ffmpeg_utils.py` / `scene_detection.py` / `clip_selection.py` | pure functions over paths/segments | import | DEEP: the test suite's best-covered seam (see `tests/`). |
| `cloud/` package | billing, auth, metering, storage | `BILLING_ENABLED` flag | Correctly optional: zero imports when off. Keep it that way. |
| `mcp_server.py` | JSON-RPC tools at `POST /mcp` | in-process `httpx.ASGITransport` back into this app | DEEP by construction: can never drift from REST behaviour. |

### Backend seams to create next (ordered by leverage — T6a/b, T7, T8a done)

1. T6c job-core routers + `deps.py` — `/api/process`, `/api/status`, `/api/edit`,
   `/api/clip/*`, `/api/render`, `/api/subtitle`, `/api/hook`, `/api/translate`;
   shared helpers move to `deps.py`, routers drop the `_app()` shim.
2. T8b `pipeline/` stages — `download.py`, `detect.py`, `render.py` (tracking done).
3. Config values freeze at import (conftest pins test-assumed vars); a lazy
   `get_settings()` is NOT planned — freezing is load-bearing for tests.

## Frontend (React 18 / Vite / Tailwind)

| Module | Interface | Seam | Depth |
|---|---|---|---|
| `App.jsx` | boot, job submit, polling, results | `#root` | DEEPENING: 1,732 → 1,658 lines (keys → `useApiKeys`, crypto → `lib/crypto`, modals lazy). Results grid stays until `useJob` (see plan T10). |
| `lib/crypto.js` ✨ NEW | `encrypt(text)` / `decrypt(text)` | `src/lib/crypto.js` | DEEP: 40 lines out of `App.jsx`; honest docs (obfuscation, not encryption). |
| `hooks/useApiKeys.js` ✨ NEW | key state pairs + persistence | `src/hooks/useApiKeys.js` | DEEP: 5 states + 4 effects behind one call; callers unchanged. |
| `lib/renderInBrowser.js` | same async `renderInBrowser()` | dynamic `import()` | DEEPENED: 1 MB renderer loads on first use, not boot. |
| `lib/api.js` | `apiFetch` / `apiJson` + `QuotaError`/`ApiError` | fetch wrapper | DEEP: bearer + 402 handling in one place. Keep. |
| `ResultCard.jsx` | props per clip (`clip`, `jobId`, keys…) | `memo()` boundary ✨ NEW | Now memoized + its 4 modals lazy-split: an N-clip grid no longer re-renders N cards per poll tick. |
| `ClipEditor.jsx` (1,603 lines) | `jobId`/`clipIndex`/`onRerendered` | lazy chunk | Already uses `useMemo`/`useCallback`/`useDeferredValue` internally — good; the win was loading it on demand. |
| `ui/` (`Modal`, `SegmentedControl`, `StepIndicator`) | shared primitives | component props | DEEP: the design-system seam. All new UI must go through these, never hand-rolled modals. |
| `design.md` + `tokens.css` | Lumen · Night Foundry tokens | CSS vars + Tailwind aliases | The anti-slop contract: brass accent, two-register type, zero gradients/glass. UI work extends this file, never bypasses it. |

### Frontend seams to create next (T9 done as `useApiKeys`)

1. `hooks/useJob.js` — polling + status state out of `App.jsx`.
2. `components/ResultsGrid.jsx` — blocked on `useJob` (prop-drilling 20 props
   without it is shallower, not deeper; see plan T10).

## Data / infra

- `uploads/` + `output/` — gitignored runtime dirs, bounded by `UPLOADS_MAX_GB` / `OUTPUT_MAX_GB` caps + age sweep. Never commit media.
- 63 MB `churchil_queen_vertical.gif` + demo `.mp4`s are tracked in git — the repo's clone-time tax. Migrate to release attachments / R2; keep only `dashboard/public/demo/*` in-tree (`clip-source.mp4` already removed as unreferenced).
- `yolov8n.pt` is correctly gitignored (`*.pt`) and pre-downloaded in Docker build.
