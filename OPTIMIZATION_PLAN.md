# Optimization plan — OpenShorts

## BUGFIX + CLEANUP PASS (all suite errors fixed, codebase swept)

Backend suite: **506/506 passed** (was 452 passed + 11 failed + 3 errors).
Frontend: `npm run lint` clean, `vite build` green. Pyflakes clean.

| # | Root cause | Fix |
|---|---|---|
| 1 | `test_generation_controls` read `gemini_worker.py` with locale (cp1252) decoding → crash on UTF-8 bytes | test helper opens with `encoding="utf-8"` (3 tests) |
| 2 | `sqlalchemy` etc. never installed (billing requirements) → 3 collection errors + 2 MCP cloud failures | `pip install -r requirements-billing.txt` (repo's own pins) |
| 3 | `recut.py` captioner contract grew `style_override=`; test double was stale | fake accepts `style_override=None`, matching `auto_caption_clip` |
| 4 | Personal `.env` (`DISABLE_YOUTUBE_URL=true`) leaked into tests via import-time freeze | conftest pins `DISABLE_YOUTUBE_URL=0`, `MIN_SOURCE_SECONDS=45` (same philosophy as existing BILLING pin) |
| 5 | Gate tests posted URL-only jobs; pipeline now *requires* a transcript (Whisper removed) | pass-through tests attach a minimal `.srt` via multipart (endpoint's documented path); rejection tests stay transcript-less, pinning gate-before-transcript order |
| 6 | **Latent crash found by pyflakes:** `httpx` used in webhook delivery but its mid-file `import httpx` moved away with the social block → `NameError` on first webhook | top-level `import httpx` in app.py (no test covered that path) |
| 7 | Dead imports after extraction (itertools, timedelta, BackgroundTasks, HTMLResponse, 5× s3 helpers, LAYOUT_*/TIKTOK re-exports, publish_jobs, scenedetect×3, JUMP re-export, numpy, 2× dead locals, 2× `f`-without-placeholders) | removed; all verified via suite + HTTP checks |

Disk: `__pycache__` trees + `.pytest_cache` cleared. `output/`/`uploads/` are live
job data under retention caps — left alone. 63 MB tracked gif stays T11
(coordinated history rewrite only).

## UNUSED-FILE SWEEP (12 tracked files removed, 210 deletions)
Deleted only after proving zero references (import/usage/content grep across
code, configs, Docker, docs, SEO): `verify_aesthetic.py`,
`verify_custom_hook.py`, `verify_hooks.py` (one-off scripts); `App.css`,
`react.svg`, `vite.svg` (unimported Vite scaffolding); `demo/clip-source.mp4`
(540 KB, unreferenced — `clip-vertical.mp4` stays, used by WatermarkModal);
`cli/openshorts.egg-info/*` (tracked build output) + `*.egg-info/` gitignored.
Disk-only scratch removed (gitignored): 8 root probe scripts, 2 mp3s.
Kept deliberately: `server.json` (MCP registry manifest), `make_watermark.py`
(generates tracked `watermark.png`, used by main.py), `openrouter_client.py`
(provider compat shim), `remotion/` (render-service bundles it — live copy,
byte-identical preview copy in dashboard is by design), CLI, examples, skills,
screenshots, run/stop bats, churchil/demo media (T11). Suite still 506/506;
frontend lint + build green after removals.

Status ledger for the structure / performance / UI pass. Done items are
verified (eslint + `vite build` + pytest subset). Next items are ordered by
leverage-per-risk; each names its Module, the Seam, and the deletion test.

## DONE

- [x] **T0 — disk cleanup.** Deleted `backend-boot.log`, 0-byte `test1.mp4`,
  `__pycache__` trees. `demo-openshorts.mp4` stays (referenced by README/landing).
  Rule going forward: runtime media never commits (`uploads/`, `output/`,
  `*.mp4`, `*.pt` already gitignored).
- [x] **T1 — new Module `dashboard/src/lib/crypto.js`.** Extracted the XOR+Base64
  key obfuscation out of `App.jsx` behind `encrypt`/`decrypt`. Interface is two
  functions; behavior identical (same salt, same `ENC:` prefix, same fail-closed
  corrupt path, same plaintext back-compat). `App.jsx` shrank by ~40 lines.
  Verified: eslint clean, build passes, key save/load paths untouched.
- [x] **T2 — lazy-split heavy modals in `App.jsx`.** `ClipEditor`, `ReframeEditor`,
  `ScheduleWeekModal`, `TopUpModal`, `PlanChoiceModal`, `TrialUpgradeModal`,
  `LoginModal` are now `React.lazy` + `Suspense fallback={null}` at each usage
  site. Build output proves the split: `ClipEditor-*.js` 38 KB, `ReframeEditor`
  9 KB, `ScheduleWeekModal` 9.5 KB, `TopUpModal` 5.8 KB load on first open,
  not on boot. Functional contract untouched (same props, same gating).
- [x] **T3 — `ResultCard` memo + modal split.** Default export wrapped in
  `memo()`; `SubtitleModal`, `HookModal`, `TranslateModal`, `WatermarkModal`
  lazy-split with `Suspense` boundaries. An N-clip grid no longer re-renders
  N cards per 2s poll tick, and no longer pays 4 modals × N cards up front
  (`SubtitleModal-*.js` 15 KB now on demand). Fixed a real bug found by lint:
  the `memo(` wrapper needed its closing paren.
- [x] **T4 — docs.** `ARCHITECTURE.md` (module/interface/seam/depth map for
  backend + frontend + infra) and this file. `design.md` (Lumen system) left
  authoritative for all visual decisions — no token, radius, or copy-voice
  changes in this pass.
- [x] **T5 — verification.** `eslint` clean on all touched files; `vite build`
  succeeds with the new chunks; `pytest tests/test_ffmpeg_utils.py
  tests/test_clip_selection.py tests/test_log_view.py` → 36 passed.
- [x] **T7 — `config.py`.** All env-derived constants + `LAYOUT_ENV`/`LAYOUT_IMPLIES`
  /`layout_env()` behind one Module seam. `app.py` re-exports every name so
  `app_module.<name>` keeps working. Verified over real HTTP: `/health`,
  `/api/config`, `/api/llm/models`, `/gallery` 200; `/video/nope` 404.
- [x] **T6a — `state.py` + `routers/` (first slice).** `jobs`, `publish_jobs`,
  `job_queue`, `_enqueue_job`, semaphore in `state.py` (same objects — the
  test suite mutates `app_module.jobs` directly and still passes). `routers/`
  follows the existing `mcp_server.router` idiom: each module exposes only
  `router`. Moved: `system.py` (/health, /api/config, /api/env×2,
  /api/llm/models + /api/openrouter/models) and `gallery.py` (/gallery,
  /video/{id}). app.py 4,327 → ~3,985 lines. Full suite: 452 passed with
  byte-identical pre-existing failures (11 failed + 3 errors on the pristine
  tree too: missing sqlalchemy/cloud env, template-band drift, network gates).
  Zero regressions.

## NEXT (ordered, do one at a time)

- [x] **T6b — `routers/social.py`.** All 8 `/api/social/*` handlers +
  `SocialPostRequest` + social-private helpers moved; AST-proven equivalent to
  the originals (13/13 blocks). Shared helpers stay in app.py, reached via
  `import app as _app` at call time (cycle-free: app imports the router while
  partial, attributes resolve per request). Hardening: first cut used a
  module-top import (order-dependent — importing the router before app raised
  AttributeError); now a lazy `_app()` accessor, module imports standalone. One real bug caught by the suite:
  the tenant test patched `app_module._upload_post_get`, which no longer
  affects the router's binding — the test now patches `routers.social`
  (same behavior asserted). Full suite back to exact baseline (11+3
  pre-existing, 452 passed). app.py 4,327 → ~3,610 lines.
- [x] **T8a — `pipeline/tracking.py`.** `SmoothedCameraman` + `SpeakerTracker`
  (+ `ASPECT_RATIO`, `JUMP_CONFIRM_FRAMES` after two hidden couplings surfaced
  as NameErrors: default-arg and runtime reads). main.py re-exports all four.
  Module imports on numpy alone — no torch/cv2/mediapipe. main.py
  1,864 → ~1,610 lines.
- [ ] **T7 — central `config.py`.** One `get_settings()` Module replacing 40+
  `os.environ.get` sites in `app.py`. Small interface, every caller + test
  crosses it. Add `pydantic-settings` or a frozen dataclass; keep env names.
- [ ] **T8 — split `main.py` pipeline stages.** `pipeline/transcribe.py`,
  `scenes.py`, `select.py`, `render.py` with the job-dict as the single shared
  Interface. Keep `layout_picker.apply()` as the only layout seam (additive
  only — never override explicit user choice; the 92% accuracy result depends
  on the 12-frames@1024px closed-choice design).
- [x] **T9 — `hooks/useApiKeys.js`.** Key state (gemini/upload-post/
  elevenlabs/fal/userId) + persist effects behind one hook seam; App.jsx uses
  the same names. 1,732 → ~1,658 lines.
- [x] **T12 — renderer on demand.** `lib/renderInBrowser.js` dynamically imports
  `@remotion/web-renderer` + composition. Initial chunk 1,148 KB → 3 parallel
  chunks (437+407+211 KB) + 90 KB renderer on first in-browser render. Zero
  interface change (all 5 call sites already await).
- [ ] **T10 — `components/ResultsGrid.jsx`. BLOCKED on `useJob`, on purpose.**
  The grid (~130 lines JSX + ~150 lines handlers) shares ~20 pieces of App
  state (results, jobId, keys, bulkSub, durableClips, clip-edit state). Lifting
  only the JSX means prop-drilling 20 props: a *shallower* interface with no
  depth gained — the wrong move per the deletion test. Extract `useJob`
  (status/polling/results/clip-state) first; the grid then falls out trivially.
- [ ] **T6c — job-core routers + `deps.py`.** Move `/api/process`, `/api/status`,
  `/api/edit`, `/api/clip/*`, `/api/render`, `/api/subtitle`, `/api/hook`,
  `/api/translate` behind routers/. Unblocks the honest fix: shared helpers
  (`resolve_upload_post`, `_assert_job_owner`, `_ensure_job_files`, …) move to
  `deps.py`, routers drop the `_app` call-time shim.
- [ ] **T8b — pipeline stages.** `pipeline/download.py` (yt-dlp),
  `pipeline/detect.py` (face/YOLO/MediaPipe globals + frame helpers),
  `pipeline/render.py` (reframe orchestrator). tracking.py proves the pattern.
- [ ] **T11 — repo diet.** 63 MB `churchil_queen_vertical.gif` + 2.6 MB short
  gif dominate clone time. Move to release attachments / R2, keep only
  `dashboard/public/demo/*` in-tree. Needs a history rewrite (`filter-repo`)
  coordinated with all clones — do NOT do casually.
- [ ] **T12 — initial-chunk diet.** `index-*.js` is still 1.1 MB (Remotion +
  mediabunny encoders). Lazy the Remotion preview route and the encoder
  imports; consider `manualChunks` for vendor splits. Measure with
  `rollup-plugin-visualizer` before cutting.

## Non-goals (this pass, on purpose)

- No visual redesign: the Lumen system (`design.md` + `tokens.css`) is the
  anti-slop contract and stays authoritative. No new fonts, colors, gradients,
  or icon packs.
- No provider/pipeline behavior changes: layout picker, reframing modes,
  metering, and MCP semantics untouched.
- No backend file moves yet: T6–T8 need the `jobs.py` store seam first, else
  the split just relocates imports without adding depth.

## SUBTITLE PASS (sync + view-style parity)

Analysis: word times were trusted verbatim from user transcripts (no offset
control anywhere); evenly-spread .txt/.md words drift ~0.3s+. Preview chunked
at 20ch/2.0s like the server modal-burn (parity held), but sat at bottom 10%
vs burned ~15% and had no `box`-effect branch; the dubbed re-transcription
path called a function that unconditionally raises (500 on dubbed subtitles).
Killed ideas: min-event-duration floor (overlapping ASS events double-render).

- `time_offset` (±5s clamp) end-to-end: `_collect_word_blocks` shift/clamp/drop
  (zero-length collapse drops) → `generate_ass`/`generate_srt` →
  `SubtitleRequest.time_offset` → modal Sync-offset slider (±1s, 0.1 step) →
  Remotion `timeOffsetMs` (same shift semantics in `groupCaptionsIntoBlocks`).
- Parity: preview bottom 15% (= SAFE_MARGIN_V), `box` branch (white text +
  highlight outline, stroke replaced like the burn), `box` added to animation
  options + preset mapping so Boxed is representable.
- Dead code removed: `transcribe_audio` + `generate_srt_from_video`; dubbed
  clips use the stored transcript; `subtitle_minutes_for` always 0 (the
  Whisper compute it charged for no longer exists) + metering test updated.
- 5 new offset tests. Suite 511/511; tsc clean on edited TS; build green.
- External-source note: no web access in this environment; viral-caption
  conventions taken from in-repo evidence (preset table, AUTO_STYLE selection
  notes, PRD) — no outside claims made.
