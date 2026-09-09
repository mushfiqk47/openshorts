# OpenShorts

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Open Source](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://opensource.org/)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Tests](https://img.shields.io/badge/Tests-506%20Passed-brightgreen.svg)](tests/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

**OpenShorts** is an open-source, GPU-first AI video platform and automated shorts engine. It transforms long-form videos (podcasts, livestreams, webinars, tutorials) into viral, high-retention 9:16 vertical shorts for **TikTok**, **Instagram Reels**, and **YouTube Shorts**.

It brings together 3 tools in one unified platform:
1. **Clip Generator** — Intelligent viral moment detection, AI vertical reframing, and Remotion dynamic karaoke subtitles.
2. **AI Shorts (UGC Creator)** — Generates full marketing videos with AI actors, voiceover, b-roll, and lip-sync from a single URL or description.
3. **YouTube Studio** — AI thumbnails, 10 viral title suggestions, and chapter descriptions.

---

## ⚡ What's New & Key Highlights

- **Multi-LLM Intelligence (`llm_client.py`)**: Built-in support for **Local Ollama** (default `llama3.2:1b`), any **OpenAI-compatible endpoint** (LM Studio, vLLM, LocalAI, Together, Groq, DeepSeek, OpenAI), as well as **Google Gemini** (`gemini-2.5-flash`, `gemini-2.5-flash-lite`).
- **GPU-First Pipeline**: Native support for **NVIDIA NVENC** FFmpeg hardware encoding (`FFMPEG_ENCODER=nvenc`), **CUDA-accelerated YOLOv8** face tracking, and **TransNetV2** boundary detection.
- **Dynamic Remotion Subtitle Engine**: Word-by-word karaoke highlighting, custom Anton typography, pop animations, and safe-zone positioning (`SAFE_MARGIN_V = 43`) to prevent TikTok/Reels UI clipping.
- **Smart 9:16 AI Layouts**: 6 specialized layout modes: **TRACK** (single speaker), **GENERAL** (blurred background), **SPLIT** (stacked interview two-shot), **SCREENCAST** (slides + presenter), **CAMERA INSET** (OBS/streamer webcam zoom), and **PUNCH-IN** (audio beat zoom).
- **Live Environment Sync (`env_manager.py`)**: Update API keys and engine parameters directly from the Dashboard Settings panel with instant persistence to `.env` and automatic secret masking.
- **Agent Automation Ready**: Native **Model Context Protocol (MCP)** server at `/mcp`, standard **Agent Skills** integration, and HMAC-signed webhook delivery (`X-OpenShorts-Signature`).
- **1-Click Local Launchers**: Zero-Docker Windows batch launchers (`run.bat`, `run-full.bat`, `stop.bat`) for fast local iteration.

---

## Self-Hosted vs Hosted

| Feature | Self-Hosted (This Repo) | Hosted ([openshorts.app](https://www.openshorts.app/)) |
|:---|:---|:---|
| **Price** | Free forever (MIT License) | Free plan, paid plans from $12/mo |
| **Speed** | 5-8 min on CPU / ~50s on NVIDIA GPU | ~50s on dedicated NVIDIA cloud GPUs |
| **AI Models** | Local Ollama, OpenAI-compatible, or BYOK Gemini | Gemini included; zero setup required |
| **Watermark / Limits** | None, ever | Watermark and 20 min/mo on free tier |
| **Data Privacy** | 100% on your own machine/server | Hosted cloud storage |
| **MCP / Agent API** | Local `/mcp` endpoint | Always-on endpoint at `mcp.openshorts.app` |

---

## 3 Tools in 1 Platform

### 1. Clip Generator
Turn your podcasts, interviews, tutorials, and speeches into platform-ready shorts:
- **Viral Moment Detection**: Multi-LLM analysis scans transcripts and scene boundaries to discover 3-15 high-engagement moments.
- **AI Subject Tracking**: MediaPipe Face Mesh + YOLOv8 fallback with `SmoothedCameraman` stabilization to eliminate jitter.
- **Speaker Isolation & Split Screen**: Stacks two participants in podcast interviews using mouth-activity normalization (`active_speaker.py`).
- **Dynamic Karaoke Subtitles**: Word-level timing, pop effects, and customizable color schemes.
- **AI Voice Dubbing**: Translate and dub video voiceovers into 30+ languages via ElevenLabs.

### 2. AI Shorts (UGC Video Creator)
Generate marketing videos with AI actors for any product or business without cameras or studios:
- **Cost Modes**: Low Cost (~$0.65/video) and Premium (~$2.00/video).
- **Automated Scripting**: Scrapes your landing page to craft viral Hook → Problem → Solution → CTA scripts.
- **AI Actor & Lip-Sync**: Flux 2 Pro actor generation, Hailuo 2.3 Fast img2video + VEED Lip-sync or Kling Avatar v2.
- **B-Roll Visuals**: Auto-generated contextual image b-roll with smooth Ken Burns motion transitions.
- **Social Distribution**: Auto-publish directly to TikTok, Instagram Reels, and YouTube Shorts.

### 3. YouTube Studio
- **Viral Title Generator**: 10 high-CTR title variations with interactive chat refinement.
- **AI Thumbnail Generator**: Smart face extraction and custom background overlay.
- **Timestamped Chapters**: Automated descriptions generated directly from transcript boundaries.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **FFmpeg** (must be accessible in your system `PATH`)
- **Node.js 18+** & **npm**
- *(Optional)* **Docker & Docker Compose**
- *(Optional)* **NVIDIA GPU with CUDA** for hardware acceleration
- *(Optional)* **Ollama** running locally (`ollama run llama3.2:1b`) or Gemini API Key

---

### Option A: Local Launchers (Windows, No Docker)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mushfiqk47/openshorts.git
   cd openshorts
   ```

2. **Configure your environment:**
   ```bash
   cp .env.example .env
   ```

3. **Run the application:**
   - **Clips-Only Launcher (`run.bat`)**:
     Starts the FastAPI backend (:8000) and the Vite frontend (:5175).
     ```cmd
     run.bat
     ```
   - **Full Stack Launcher (`run-full.bat`)**:
     Starts Backend (:8000), Remotion Render Service (:3100), and Frontend (:5175).
     ```cmd
     run-full.bat
     ```

4. **Shutdown all services:**
   ```cmd
   stop.bat
   ```

---

### Option B: Docker Compose

```bash
# Build and run the entire stack
docker compose up --build
```
- Frontend: `http://localhost:5175`
- Backend API: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`

---

### Option C: Manual Development Setup

#### Backend
```bash
# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend (Dashboard)
```bash
cd dashboard
npm install
npm run dev
```

#### Remotion Render Service (Optional)
```bash
cd render-service
npm install
npm run build
node dist/server.js
```

---

## 🧠 Supported LLM Providers

OpenShorts abstracts LLM communication through [`llm_client.py`](llm_client.py), supporting multiple backends:

### 1. Local Ollama (Default)
Run completely offline and free of cost:
```bash
ollama run llama3.2:1b
```
Configure in `.env`:
```env
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2:1b
LLM_API_KEY=ollama
```

### 2. Any OpenAI-Compatible Provider
Compatible with **LM Studio**, **vLLM**, **LocalAI**, **Groq**, **DeepSeek**, **Together AI**, or **OpenAI**:
```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=your_api_key_here
```

### 3. Google Gemini
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 📐 AI Reframing & Layout Modes

OpenShorts automatically reframes 16:9 landscape content into 9:16 vertical video without awkward black bars:

| Layout Mode | Description | Trigger / Implementation |
|:---|:---|:---|
| **TRACK** | Centers on the active speaker with MediaPipe face detection and YOLOv8 fallback. | Single speaker footage (`SmoothedCameraman`) |
| **GENERAL** | Letterboxed with a blurred, color-matched ambient background. | Wide landscapes, crowds, or group shots |
| **SPLIT** | Vertically stacks two speakers in half-frames; active speaker is tracked. | `SPLIT_LAYOUT=1` (`split_layout.py` + `active_speaker.py`) |
| **SCREENCAST** | Stacks slide presentations, browser captures, or screen shares above the presenter. | `SCREENCAST_LAYOUT=1` (`screencast_layout.py`) |
| **CAMERA INSET** | Detects corner webcam overlays (e.g. OBS or gaming streams) and enlarges the host. | Automated geometric detector (`camera_inset.py`) |
| **PUNCH-IN** | Dynamic ~12% camera push on audio beats or emphasis words for visual rhythm. | `PUNCH_IN=1` (`punch_in.py`) |
| **AUTO** | Analyzes 12 sampled frames via Gemini to select the optimal layout per video. | `layouts: ["auto"]` (`layout_picker.py`) |

---

## 📝 Transcription & Subtitle Engine

- **User-Supplied Transcripts**: High-precision clipping requires a transcript file (`.srt`, `.vtt`, `.txt`, `.md`, or `.json`) with word-level timestamps provided at submission.
- **Word Continuation Merging**: Automatically concatenates Whisper continuation tokens (e.g., compound words, hyphenated phrases) to maintain proper word boundaries.
- **Time Offset Nudging**: Includes manual or automatic `time_offset` sync adjustment to correct audio-text drift.
- **Remotion Dynamic Captions**:
  - Word-level karaoke highlighting (active word pops with `#FFE500` yellow).
  - Heavy black stroke outlines for legibility across light and dark scenes.
  - Safe-zone bottom margin (`SAFE_MARGIN_V = 43`) prevents captions from overlapping platform user interfaces.

---

## 🤖 Agent Integration: MCP, REST API & Webhooks

The entire OpenShorts pipeline is built for autonomous AI agents and automation tools.

### Model Context Protocol (MCP) Server (`/mcp`)
OpenShorts exposes a built-in streamable HTTP JSON-RPC MCP server at `/mcp`:
```bash
# Add to Claude Code or Cursor
claude mcp add --transport http openshorts http://localhost:8000/mcp
```

**Available MCP Tools:**
- `process_video`: Submit video URL/path with transcript for automated clipping.
- `get_job_status`: Poll pipeline progress, logs, and clip metadata.
- `list_clips`: Retrieve all rendered clips with download URLs and titles.
- `add_subtitles`: Re-render clips with custom subtitle presets.
- `publish_clip`: Dispatch clips to TikTok, Instagram, and YouTube.

### REST API & Webhooks
Submit jobs and receive signed asynchronous delivery upon completion:
```bash
curl -X POST http://localhost:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=...",
    "transcript": "1\n00:00:01,000 --> 00:00:04,000\nWelcome to our podcast...",
    "layouts": ["auto", "punch_in"],
    "webhook_url": "https://your-server.com/webhook",
    "webhook_secret": "secret_key_123"
  }'
```
Payloads include HMAC-SHA256 signatures in the `X-OpenShorts-Signature` header for secure verification.

### Python CLI
```bash
# Process a local video with transcript
python main.py -i video.mp4 --transcript video.srt
```

### Agent Skill Standard
Standard [Agent Skills](https://agentskills.io) definition available in [`skills/openshorts/SKILL.md`](skills/openshorts/SKILL.md).

---

## 🛠️ Project Architecture

```
openshorts/
├── app.py                  # FastAPI composition root and core job execution
├── config.py               # Centralized configuration & environment parsing
├── state.py                # Singleton job queue, job registry, and semaphores
├── env_manager.py          # Live .env read/write sync with secret masking
├── llm_client.py           # Multi-provider LLM abstraction (Ollama, OpenAI, Gemini)
├── main.py                 # Core video processing pipeline composition
├── subtitles.py            # Subtitle styling, SRT generation, ASS burning, and sync
├── ffmpeg_utils.py         # Hardware encoding flags (NVENC/x264), probe, filter graphs
├── reframe_v2.py           # Subject detection, face tracking, and 9:16 re-framing
├── layout_picker.py        # Frame-sampled LLM layout selection (split/screencast/track)
├── split_layout.py         # Dual-speaker vertical interview stack layout
├── screencast_layout.py    # Presentation + speaker composition
├── camera_inset.py         # OBS / stream webcam extraction layout
├── punch_in.py             # Audio-beat dynamic punch-in zoom
├── active_speaker.py       # Normalized lip-activity speaker detection
├── mcp_server.py           # Model Context Protocol (MCP) streamable HTTP server
├── routers/                # Modular FastAPI route clusters
│   ├── system.py           # /health, /api/config, /api/env, /api/llm/models
│   ├── gallery.py          # /gallery, /video/{id} SEO pages
│   └── social.py           # /api/social/post, profiles, analytics, scheduling
├── pipeline/
│   └── tracking.py         # SmoothedCameraman & SpeakerTracker (pure numpy)
├── dashboard/              # React 18 + Vite 4 + Tailwind CSS web interface
│   ├── src/
│   │   ├── App.jsx         # Dashboard application root with lazy-loaded modules
│   │   ├── hooks/          # Custom hooks (e.g. useApiKeys)
│   │   ├── lib/            # Utilities (crypto.js, api.js, renderInBrowser.js)
│   │   └── components/     # UI modals, ResultCard, ClipEditor, SubtitleModal
│   └── remotion/           # React Remotion compositions for subtitle preview
├── render-service/         # Node.js Remotion server-side rendering service
├── cli/                    # Zero-dependency command-line client
├── examples/               # Automation workflows (e.g., n8n content machine)
└── tests/                  # Pytest test suite (506 tests)
```

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
|:---|:---|:---|
| `LLM_PROVIDER` | `ollama` | LLM backend: `ollama`, `openai_compatible`, `gemini` |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Base URL for Ollama or OpenAI-compatible endpoint |
| `LLM_MODEL` | `llama3.2:1b` | Model name for viral moment detection |
| `LLM_API_KEY` | `ollama` | API key (set if using remote OpenAI-compatible provider) |
| `GEMINI_API_KEY` | *(optional)* | Google Gemini API key for fallback or Gemini mode |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `FFMPEG_ENCODER` | `nvenc` | Video encoder: `nvenc` (NVIDIA GPU), `x264` (CPU), `auto` |
| `YOLO_DEVICE` | `cuda` | Vision device for YOLOv8: `cuda`, `cpu`, `auto` |
| `TRANSNETV2_DEVICE` | `cuda` | Scene boundary detector device: `cuda`, `cpu`, `auto` |
| `MAX_CONCURRENT_JOBS` | `5` | Maximum simultaneous video processing jobs |
| `CLIP_WORKERS` | `2` | Parallel worker processes for clip extraction |
| `DISABLE_YOUTUBE_URL` | `false` | When `true`, restricts inputs to local uploads only |
| `MAX_FILE_SIZE_MB` | `2048` | Maximum video upload size in Megabytes (2GB) |
| `OUTPUT_MAX_GB` | `25` | Storage quota cap for generated clips directory |
| `UPLOADS_MAX_GB` | `15` | Storage quota cap for source video uploads |
| `JOB_RETENTION_SECONDS`| `86400` | Duration to retain completed jobs on disk (24 hours) |
| `BILLING_ENABLED` | `false` | Enable commercial billing tier (optional `cloud/` package) |

---

## 🧪 Testing & Validation

The codebase includes an extensive automated test suite covering all pipeline components, layout engines, reframing logic, and endpoints:

```bash
# Run full pytest suite
python -m pytest tests/ -q
```
*Result: 506 / 506 tests passing.*

To run linting on the dashboard:
```bash
cd dashboard
npm run lint
npm run build
```

---

## 🤝 Contributing

Contributions are welcome! Whether it's adding new AI models, refining face tracking heuristics, improving Remotion subtitle themes, or optimizing FFmpeg filtergraphs:
1. Fork the repo.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'feat: add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📄 License

OpenShorts is open-source software licensed under the **[MIT License](LICENSE)**.

*Exception:* The optional [`cloud/`](cloud/) directory (multi-tenant billing and managed keys infrastructure) is source-available under the OpenShorts Commercial License. Self-hosting and running OpenShorts for personal or internal use never requires this directory.
