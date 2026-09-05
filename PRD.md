# OpenShorts — Product Requirements Document

**Version:** 1.0 — 2026-09-02  
**Status:** Living document derived from current codebase (self-hosted + hosted)  
**Product:** OpenShorts.app — Open-source AI video platform (3 tools in 1)

---

## 1. Executive Summary

OpenShorts transforms long-form video (podcasts, webinars, livestreams, vlogs, interviews) and text/product URLs into viral-ready vertical short clips (9:16) for TikTok, Instagram Reels, and YouTube Shorts. It also provides a YouTube Studio toolkit and an AI Shorts (UGC) generator with AI actors.

**Two distribution modes, same software:**
- **Self-hosted (open-source, MIT):** User runs Docker locally. No watermark/limits, uses their own AI/service credentials.
- **Hosted (openshorts.app):** Managed GPU, AI included, subscription plans, free plan with watermark + monthly minute limit, paid from $12/mo.

Product is already shipped and validated. This PRD codifies current behavior, user flows, and requirements for ongoing development.

---

## 2. Goals & Non-Goals

### Goals
1. Reduce time from long video → publishable shorts from hours to < 2 minutes of operator work.
2. Provide an open-source, self-hostable alternative to closed competitors with no watermark/limits in self-host.
3. Offer a hosted path that covers hardware + AI costs with transparent pricing.
4. Enable automated / agentic workflows (MCP, REST, Webhooks, CLI) without using the dashboard.

### Non-Goals (v1)
- Full NLE timeline editor.
- Native mobile apps.
- Live streaming / recording inside the product.

---

## 3. Target Users & Personas

| Persona | Job-to-be-done | Key need |
|---|---|---|
| **Creator** | Turn weekly podcast/vlog into 5-10 shorts | Speed, quality reframing, one-click publish |
| **Marketing Agency** | Produce UGC for multiple clients at scale | Batch generation, no actors/studio, gallery |
| **SaaS Founder** | Demo/product marketing from just a URL | URL → script → AI actor → publish |
| **E-commerce / Local SMB** | Affordable vertical ads | Low-cost generation, scheduling, multi-platform post |
| **Developer / Power User** | Automate pipeline via API/MCP | Stable API, webhooks, BYOK self-host |

---

## 4. Product Scope — 3 Tools in 1

### 4.1 Clip Generator (Core)
**Input:** Local upload (file picker / drag-drop) or hosted URL ingest. Upload limit 2 GB. Minimum source duration ~45s (configurable) to avoid degenerate clips.

**Output:** 3–15 clips per source, each 15–60s, vertical 9:16 (also Square 1:1 and Horizontal passthrough), with:
- Viral moment selection (AI picks start/end, title, descriptions, viral hook text)
- Smart reframing (see §7)
- Burned-in subtitles (default on, re-styleable per clip or bulk)
- Hook text overlay (optional, multiple styles)
- Optional AI video effects (FFmpeg filter pipeline)
- Optional voice dubbing / translation (30+ languages)
- Watermark handling: self-host never; hosted free plan = watermark, paid = no watermark

### 4.2 AI Shorts — UGC Video Creator
**Input:** Product/business description (free text) OR website URL (scrape + research).
**Pipeline:** Analyze → Script (hook-problem-solution-CTA) → Actor (generate portrait or pick from shared gallery / uploaded photo) → Voiceover (TTS) → Talking-head video + lip-sync → B-roll generation + Ken Burns → FFmpeg composite (subtitles + hooks) → Gallery + Publish.
**Cost modes:** Low Cost (~$0.65/video) and Premium (~$2/video).
**Gallery:** Public UGC gallery (`/gallery`) with hover-to-play, individual SEO pages (`/video/{id}`) with og:video + JSON-LD, avatar gallery with prompt history.

### 4.3 YouTube Studio
- AI thumbnail generator (background + face overlay)
- 10 viral title suggestions + interactive refinement chat
- Auto description with chapter timestamps (from transcript)
- One-click publish to YouTube
- Shared avatar/video gallery infrastructure (S3 public bucket)

---

## 5. User Journeys

### 5.1 First-time Self-Host
1. Clone → `docker compose up --build` → open `http://localhost:5175`
2. Settings → enter AI credentials (encrypted in browser localStorage, sent via headers only when needed, never stored server-side)
3. Clip Generator → Upload or paste URL → Set output format / clip count / hook style → Process
4. Poll status → Preview clips + original synced playback → Edit (subtitles, hooks, crop/re-cut, effects, dubbing) → Download / Download All (ZIP) / Publish / Schedule

### 5.2 Hosted Paid User
1. Sign in → choose plan (or trial) → no keys to enter (AI managed)
2. Same flow as above; minutes metered, concurrency/priority by plan, clips archived to durable storage, email notification on completion, optional webhook.

### 5.3 Agentic / Automated
- Via MCP (`/mcp`): `process_video`, `get_job_status`, `list_clips`, `get_quota`, `add_subtitles`, `publish_clip`
- Via REST (`/api/process` + `/api/status/{job}` + `/api/edit` + `/api/subtitle` + `/api/hook` + `/api/translate` + `/api/social/post` + `/mcp` JSON-RPC)
- Via Webhook: `webhook_url` + optional `webhook_secret` (HMAC-SHA256, `X-OpenShorts-Signature`) → exactly one POST at terminal state, after archive so payload can carry durable download links
- Via CLI (`cli/` + `openshorts` pip package) and n8n workflow (`examples/n8n/`)

---

## 6. Functional Requirements

### 6.1 Ingest
- MUST accept local file upload and URL ingest (hosted may disable URL via env flag).
- MUST validate URL is public (SSRF guard: block non-http(s), private/loopback/metadata hosts) at submit AND webhook delivery.
- MUST enforce 2 GB file limit, private/public S3 bucket support, `MAX_CONCURRENT_JOBS` (default 5) with PriorityQueue (paid plans get higher priority).
- MUST probe URL duration before metering; reject if cannot determine.
- SHOULD show pre-flight quality gate if source < 720p (configurable) and require confirmation.

### 6.2 Transcription & Scene Detection
- Word-level timestamps required (used for snap-to-word, chapters, subtitles, clip selection).
- Scene boundaries via content detector; strategy per scene: TRACK vs GENERAL vs variants (see §7).
- MUST expose progress logs streaming via `/api/status/{job}`.

### 6.3 Clip Selection & Metadata
- For each clip MUST produce: `start`, `end` (absolute seconds, 3-decimal), `video_url`, platform descriptions (TikTok/Instagram/YouTube), `viral_hook_text` (≤10 words, same language as transcript, 1–2 emojis).
- Target clip counts/durations configurable (`target_clips`, `clip_min_seconds`, `clip_max_seconds`).
- Snap cuts to word boundaries (never mid-word), prefer silence for cuts.

### 6.4 Rendering & Post-Processing
- MUST support `output_format`: `auto` / `vertical` (9:16) / `square` (1:1) / `horizontal` (passthrough, stream-copy remux).
- MUST support `layouts` parameter per job: `auto`, `split`, `screencast`, `speaker_cut`, `punch_in` (each toggles env for that job only).
- MUST allow per-job advanced controls: hook style/duration, sub style, etc.
- MUST provide endpoints: `/api/edit` (FFmpeg AI effects), `/api/subtitle` (generate + burn, bulk apply to all), `/api/hook` (burn hook), `/api/translate` (dubbing), `/api/social/post` (async publish), recut/crop overrides (force_strategy, crop_overrides).
- Captions MUST be last layer; derived files named `subtitled_<ts>_*`, `hooked_<ts>_*`, `recut_*_*` with canonical resolution to newest derived file.

### 6.5 Publishing & Scheduling
- One-click publish to TikTok, Instagram Reels, YouTube Shorts simultaneously (async upload, profile selection).
- Schedule for future date/time.
- TikTok post mode configurable (`MEDIA_UPLOAD` drafts vs `DIRECT_POST`).

### 6.6 Persistence & Recovery
- Jobs must survive restart: recover completed jobs from disk (metadata JSON) + re-enqueue mid-flight jobs via resume manifest (bounded retries).
- Auto-cleanup: `JOB_RETENTION_SECONDS` (24h self-host, 1h cloud), plus disk caps `OUTPUT_MAX_GB` (25) / `UPLOADS_MAX_GB` (15) evicting oldest.
- Project state (per-clip `active_layers`, `server_file`) must sync to backend (debounced) for reopen from History/Library after archive to R2.

### 6.7 Dashboard (Frontend)
- Stack: React 18 + Vite 4 + Tailwind 3.4.
- Tabs: Clip Generator, AI Shorts, AI Agent, UGC Gallery, YouTube Studio, History (hosted signed-in), Settings.
- Global UX: sidebar collapsible, session recovery (localStorage, 24h), synced original ↔ clip playback, logs panel, bulk subtitles, download-all ZIP, profile selector, usage meter (hosted), social connect nudge.
- SEO: build-time plugin injects crawler-visible fallback into `#root` for SPA, emits flat `.html` for `/alternatives` cluster + supporting pages, generates `sitemap.xml` + `llms.txt` from same page list. Pricing facts centralized in `seo/data.js` — update there when pricing changes.

---

## 7. AI & Media Intelligence

> Credentials and model selection are deployment configuration. The operator provides their own AI credentials (self-host) or managed credentials (hosted). No specific vendor or model name is part of this PRD.

### 7.1 Viral Moment Detection
- Use your AI provider to analyze full transcript + word timestamps + scene boundaries + video duration and return 3–15 ranked moments (15–60s each) with descriptions and hook text.
- Contract: absolute seconds, no other time format, 0 ≤ start < end ≤ duration, pad 0.2–0.4s around hook/payoff, cut on silence, no generic intro/outro unless it contains the hook.

### 7.2 Vertical Reframing — Modes
| Mode | When | How |
|---|---|---|
| **TRACK** | Single subject | Face detection + person fallback, "Heavy Tripod" stabilization with safe zone + jump confirmation |
| **GENERAL** | Groups / landscapes | Blurred background, preserve full width, centered foreground |
| **SPLIT** | Two-shot conversation, both faces visible in same frame >50% of sample | Stack both speakers in half-frames; gated on both speaking if speaker signal enabled |
| **SCREENCAST / WIDE** | Content width matters (spreadsheets/slides) | Width-fraction gate: <0.5 no-op, 0.5–0.85 stacked, >0.85 WIDE (no side crop, presenter composited on content) |
| **INSET** | Single source with webcam inset in corner | Geometric detector (small, horizontally off-center, inter-frame stable) → full-width screen + enlarged camera inset |
| **ALTERNATE (Speaker Cut)** | Speaker diarization enabled | Hard cuts to active speaker, normalized per-speaker mouth activity |
| **Punch-in** | Beat-synchronized zoom | ~12% push on audio/emphasis beats, riding TRACK crop |

Layout picker: ONE AI call per source video (12 frames @ 1024px, closed-choice: none/screencast/split) when `layouts=auto`. User explicit layout choices are additive (never disabled by AI).

### 7.3 Subtitles, Hooks, Effects, Dubbing
- Subtitles: word-timed ASS generation (max chars/duration, alignment, font, colors, highlight, effects) → FFmpeg burn.
- Hooks: styled text overlay with bundled fonts, position + duration + style selectable.
- Effects: use your AI provider to generate valid FFmpeg filter strings applied per clip.
- Dubbing/Translation: use your TTS/dubbing provider for 30+ languages with voice cloning; auto re-transcribe dubbed output for subtitle accuracy.

### 7.4 AI Shorts Intelligence
- Scrape + research product URL, generate script, TTS voiceover, portrait generation, img2video talking head + lip-sync, B-roll visuals + Ken Burns.

---

## 8. API & Integrations (Contract Only)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/process` | POST | Submit video (url or file), options: `acknowledged`, `output_format`, `target_clips`, `clip_min/max_seconds`, `auto_hook`, `layouts`, `webhook_url/secret` |
| `/api/status/{job_id}` | GET | Poll status, logs, result |
| `/api/edit` | POST | Apply generated FFmpeg effects |
| `/api/subtitle` | POST | Generate + burn subtitles (incl. bulk) |
| `/api/hook` | POST | Add hook overlay |
| `/api/translate` | POST | Dubbing |
| `/api/translate/languages` | GET | Supported languages |
| `/api/social/post` | POST | Publish/schedule to social (async) |
| `/api/keys` | POST/GET/DELETE | User API keys (cloud, session JWT only) |
| `/mcp` | POST | MCP Streamable-HTTP JSON-RPC (tools: process_video, get_job_status, list_clips, get_quota, add_subtitles, publish_clip) |
| `/docs` | GET | OpenAPI interactive docs |

**Auth:** Self-host = BYOK via headers (e.g. `X-Gemini-Key` etc.) or env fallback; Hosted = managed auth + `osk_...` API keys (`Authorization: Bearer osk_...` or `X-API-Key`), same metering/entitlement/ownership; key management refuses API-key auth.

---

## 9. Non-Functional Requirements

- **Performance:** Hosted GPU ~50s per 8-min video; self-host CPU 5–8 min. Concurrency via semaphore, configurable.
- **Reliability:** Resume manifest survives redeploys; orphan reservation refunds; DLQ not required.
- **Security:** SSRF guards, non-root container, encrypted client-side keys, upload validation (format/min size), 2 GB limit, `assert_public_url` at submit + delivery, HMAC webhook signatures.
- **Observability:** Job logs + OpenPanel analytics (opt-in, build-time gated + host allowlist; server reports job outcomes with job index for retention analysis).
- **Accessibility:** Semantic HTML, skip-to-content, keyboard-navigable sidebar/modal, focus states.

---

## 10. Configuration (Env)

| Var | Default | Meaning |
|---|---|---|
| `MAX_CONCURRENT_JOBS` | 5 | Job concurrency |
| `OUTPUT_MAX_GB` | 25 | Cap for `output/` (0 = off) |
| `UPLOADS_MAX_GB` | 15 | Cap for `uploads/` |
| `QUALITY_GATE_MIN_HEIGHT` | 720 | Warn threshold for low-res sources |
| `MIN_SOURCE_SECONDS` | 45 | Reject shorter sources |
| `JOB_RETENTION_SECONDS` | 86400 / 3600 | Self-host / cloud retention |
| `TIKTOK_POST_MODE` | MEDIA_UPLOAD | Drafts vs direct publish |
| `REFRAME_ENGINE` | v2 | v2 with fallback to v1 loop |
| `BILLING_ENABLED` | off | Enables cloud package |
| `VITE_API_URL` | — | Prod API override |
| `AWS_*`, `AWS_S3_BUCKET` | — | S3/R2 backup |

Client-side keys live in `localStorage` encrypted (XOR+Base64, prefix `ENC:`).

---

## 11. Competitive Position

See README comparison table. Differentiators: free self-host + open-source + no watermark, AI UGC actors, YouTube Studio, voice dubbing, schedule + multi-platform publish, MCP/API for agents, data stays on user server when self-hosted.

---

## 12. Pricing (Hosted)

Free plan: watermark + 20 min/mo. Paid from $12/mo for 100 min, no watermark. AI Shorts billed per video by cost mode. Metering via monthly minute ledger + per-user concurrent job limits + plan priority. One quota upsell email/day for free users out of minutes.

Centralize all pricing facts in `dashboard/seo/data.js` and never claim "free" without naming the Cloud price in same breath.

---

## 13. Release & Rollout

- Docker + Compose for self-host; hosted deploys same image with `BILLING_ENABLED=1`.
- DB migrations via Alembic (`cloud/`).
- SEO pages generated at `vite build` — no static `public/sitemap.xml`.

---

## 14. Open Risks & Decisions

- AI variance on clip selection — mitigate with closed-choice layout picker + transcript windows.
- YouTube download fragility (IP bans) — strategy chain: direct → static ISP proxies → paid proxy → fallback extractor args.
- Storage cost — disk caps + R2 archive + presigned URLs for webhooks.

---

## 15. Acceptance Criteria (v1)

- [ ] Upload or URL → 3–15 vertical clips with titles/descriptions/hooks in < 8 min (CPU) / ~50s (GPU)
- [ ] Subtitles on by default, re-styleable per clip and bulk
- [ ] Reframing correctly tracks single subject and preserves groups/screencasts per mode table
- [ ] Download single + ZIP all, publish + schedule to 3 networks, webhook fires once with durable links
- [ ] Self-host runs with only AI credentials; no watermark, no limits
- [ ] MCP tools + REST + CLI produce same results as dashboard
- [ ] Resume after restart does not lose in-flight job
