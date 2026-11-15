"""Transcription backend: NeMo-Speech.cpp running NVIDIA Parakeet TDT 0.6B v3 (GGUF, CUDA).

Every caller goes through transcribe_media(), which returns the transcript
contract the whole pipeline depends on:

    {
      "text": str,          # full punctuated transcript
      "language": str,      # ISO 639-1 code classified from the text
      "segments": [
        {"start": float, "end": float, "text": str,
         "words": [{"word": str, "start": float, "end": float}, ...]},
      ],
    }

Invariants the consumers rely on (clip cutting, karaoke subtitles, Remotion):
  - word["word"] carries a LEADING SPACE on true word starts; continuation
    fragments are merged into their base word (merge_continuation_words).
  - all numerics are native Python floats (json.dump of the transcript).
  - words sorted by start, segments chronological, absolute file timestamps.

The runtime is the prebuilt nemo-speech CLI (NVIDIA/NeMo-Speech.cpp, ggml)
with the parakeet-tdt-0.6b-v3 q8_0 GGUF on CUDA. GPU-only by design: there is
no CPU fallback, and a runtime that reports a non-CUDA backend fails loudly
instead of silently transcribing at CPU speed. Env:
  NEMO_SPEECH_BIN      CLI path (default: PATH, then the Windows installer dir)
  NEMO_ASR_MODEL       model alias or local GGUF path (default "parakeet-tdt")
  ASR_GPU_CONCURRENCY  cap on concurrent GPU transcriptions (default 1)

Parakeet TDT 0.6B v3 covers 25 European languages; the model reports no
language itself, so the code is classified from the transcript text.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import threading
import time

# Windows cp1252 can't encode the transcription emoji; force utf-8 for job logs
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from subtitles import merge_continuation_words

DEFAULT_NEMO_MODEL = "parakeet-tdt"

class _EnvSemaphore:
    """GPU gate sized from ASR_GPU_CONCURRENCY, re-read on every transcription.

    The dashboard env editor applies changes live, and a threading.Semaphore
    can't resize — so when the env value changes, a fresh gate swaps in. Jobs
    already holding the old gate finish under it; there can be a brief overlap
    at the moment of the swap, which a live settings change makes acceptable.
    """

    def __init__(self, env_key):
        self._env_key = env_key
        self._value = None
        self._gate = threading.Semaphore(1)
        self._lock = threading.Lock()

    def _current(self):
        with self._lock:
            raw = os.environ.get(self._env_key, "1").strip()
            try:
                value = max(1, int(raw))
            except ValueError:
                value = 1
            if value != self._value:
                self._value = value
                self._gate = threading.Semaphore(value)
            return self._gate

    def __enter__(self):
        self._held = self._current()
        self._held.acquire()
        return self

    def __exit__(self, *exc):
        self._held.release()
        return False


# Serializes GPU transcription across concurrent jobs so N jobs can't stack
# N model contexts / decode batches in VRAM.
_ASR_GATE = _EnvSemaphore("ASR_GPU_CONCURRENCY")

# A 3h upload decodes in minutes on GPU, but the first run may also download
# the model; keep a generous ceiling so real work is never cut off.
_ASR_TIMEOUT_SECONDS = 3600

# Subprocess output kept in error messages so self-host logs stay debuggable.
_STDERR_TAIL_CHARS = 400


_resolved_bin = None


def _resolve_nemo_bin():
    """Locate the nemo-speech CLI: NEMO_SPEECH_BIN, PATH, then the Windows installer dir.

    Memoized because every job shells out to it; env_manager resets the memo
    when NEMO_SPEECH_BIN changes live.
    """
    global _resolved_bin
    if _resolved_bin:
        return _resolved_bin
    candidates = []
    env_bin = os.environ.get("NEMO_SPEECH_BIN", "").strip()
    if env_bin:
        candidates.append(env_bin)
    on_path = shutil.which("nemo-speech") or shutil.which("nemo-speech.exe")
    if on_path:
        candidates.append(on_path)
    installer_dir = os.environ.get("LOCALAPPDATA", "")
    if installer_dir:
        candidates.append(os.path.join(
            installer_dir, "Programs", "NeMoSpeech", "bin", "nemo-speech.exe"))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            _resolved_bin = candidate
            return candidate
    raise RuntimeError(
        "nemo-speech CLI not found — it powers transcription on CUDA. Install the "
        "prebuilt release (https://github.com/NVIDIA/NeMo-Speech.cpp: run "
        "install.ps1 on Windows) or point NEMO_SPEECH_BIN at the binary.")


def reset_runtime_cache():
    """Drop the resolved-binary memo so a live NEMO_SPEECH_BIN change applies."""
    global _resolved_bin
    _resolved_bin = None


def _nemo_cache_root():
    """Where the nemo-speech runtime stores downloaded models.

    Matches model_store.cpp's cache_root(): NEMO_SPEECH_MODEL_DIR wins, then
    the Windows installer location, then the POSIX default.
    """
    env_dir = os.environ.get("NEMO_SPEECH_MODEL_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    local = os.environ.get("LOCALAPPDATA", "")
    if local and (Path(local) / "NeMoSpeech" / "models").is_dir():
        return Path(local) / "NeMoSpeech" / "models"
    return Path.home() / ".cache" / "nemo-speech" / "models"


def ensure_model_cached(model=None):
    """Make sure the configured ASR model is downloaded, pulling if needed.

    `nemo-speech pull` is idempotent: instant (prints the local path) when the
    model is cached, a full sha256-verified download when it is not. Running
    it before every transcription is what makes "next time it just works"
    true — a fresh machine or a new alias self-provisions instead of failing
    deep inside transcribe. Not gated by _ASR_GATE: downloading is network
    work, not GPU work.

    Returns (ok, detail) where detail is the local path on success or the
    failing output tail.
    """
    bin_path = _resolve_nemo_bin()
    model = model or os.environ.get("NEMO_ASR_MODEL", "").strip() or DEFAULT_NEMO_MODEL
    print(f"🎙️ Ensuring ASR model '{model}' is downloaded (first run downloads it)…", flush=True)
    try:
        proc = subprocess.run(
            [bin_path, "pull", model], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=_ASR_TIMEOUT_SECONDS)
    except Exception as e:
        return False, f"nemo-speech pull failed: {e}"
    if proc.returncode != 0:
        tail = ((proc.stderr or "") or (proc.stdout or ""))[-_STDERR_TAIL_CHARS:].strip()
        return False, f"nemo-speech pull failed ({proc.returncode}): {tail}"
    detail = ((proc.stdout or "").strip().splitlines() or ["cached"])[-1]
    return True, detail


def smoke_test_transcription():
    """End-to-end runtime check: binary + model + CUDA + a real decode.

    Generates a 2-second test tone with ffmpeg, transcribes it through the
    same CLI path real jobs use, and requires the CUDA backend line in the
    session output. No speech is expected from a tone — the point is that the
    whole GPU chain runs. Returns (ok, detail_dict) for the API/UI.
    """
    model = os.environ.get("NEMO_ASR_MODEL", "").strip() or DEFAULT_NEMO_MODEL
    remote = bool(_nemo_asr_url())
    if not remote:
        ok, detail = ensure_model_cached()
        if not ok:
            return False, {"stage": "model download", "error": detail}

    fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="asr_smoke_")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "sine=frequency=440:duration=2", "-ar", "16000",
             "-ac", "1", "-c:a", "pcm_s16le", wav_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=120)
        if remote:
            payload, elapsed = _transcribe_remote(wav_path)
            backend = str(payload.get("backend") or "")
            if "CUDA" not in backend.upper():
                return False, {"stage": "gpu check",
                               "error": f"remote backend={backend or 'unknown'}",
                               "elapsed": elapsed}
        else:
            bin_path = _resolve_nemo_bin()
            model = os.environ.get("NEMO_ASR_MODEL", "").strip() or DEFAULT_NEMO_MODEL
            started = time.time()
            proc = subprocess.run(
                [bin_path, "transcribe", wav_path, "--model", model, "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=_ASR_TIMEOUT_SECONDS)
            elapsed = round(time.time() - started, 1)
            if proc.returncode != 0:
                tail = (proc.stderr or "")[-_STDERR_TAIL_CHARS:].strip()
                return False, {"stage": "transcribe", "error": tail, "elapsed": elapsed}
            backend = "CUDA" if "backend=CUDA" in (proc.stderr or "") else None
            if not backend:
                return False, {"stage": "gpu check",
                               "error": "runtime did not report a CUDA backend",
                               "elapsed": elapsed}
            payload = json.loads(proc.stdout or "{}")
        return True, {
            "backend": backend,
            "model": model,
            "remote": remote,
            "duration_s": payload.get("duration"),
            "elapsed": elapsed,
        }
    except Exception as e:
        return False, {"stage": "smoke test", "error": str(e)}
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass


def _extract_wav(media_path):
    """nemo-speech reads PCM wav; ffmpeg-extract 16kHz mono to a temp file."""
    fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="asr_")
    os.close(fd)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", media_path,
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, timeout=1800)
    return wav_path


def _require_cuda(stderr):
    """GPU-only: the [asr] session line must report a CUDA backend.

    The release ships cpu and cuda archives; a CPU archive would transcribe
    fine and slowly, silently. Refusing keeps a misinstalled CPU runtime from
    looking like a working GPU pipeline.
    """
    for line in (stderr or "").splitlines():
        if "backend=CUDA" in line:
            return
    raise RuntimeError(
        "nemo-speech reported no CUDA backend, and transcription is GPU-only. "
        "Install the CUDA build of the prebuilt release and check the NVIDIA driver.")


def _nemo_asr_url():
    """Remote transcription endpoint (e.g. Colab + cloudflared tunnel).

    When set, transcription POSTs the wav to this server instead of running
    the local binary: the machine running OpenShorts then needs no GPU and no
    nemo-speech install. The server speaks the same JSON contract.
    """
    return os.environ.get("NEMO_ASR_URL", "").strip().rstrip("/")


def _transcribe_remote(wav_path):
    """One remote transcription round-trip. Returns (payload, elapsed_s)."""
    import httpx
    started = time.time()
    with open(wav_path, "rb") as f:
        resp = httpx.post(
            _nemo_asr_url() + "/transcribe",
            files={"file": (os.path.basename(wav_path), f, "audio/wav")},
            timeout=_ASR_TIMEOUT_SECONDS)
    elapsed = round(time.time() - started, 1)
    if resp.status_code != 200:
        raise RuntimeError(f"remote transcriber returned {resp.status_code}: {resp.text[-300:]}")
    payload = resp.json()
    backend = str(payload.get("backend") or "")
    if backend and "CUDA" not in backend.upper():
        raise RuntimeError(f"remote transcriber is not on CUDA (backend={backend})")
    return payload, elapsed


def _transcribe_with_nemo(media_path):
    remote = bool(_nemo_asr_url())
    model = os.environ.get("NEMO_ASR_MODEL", "").strip() or DEFAULT_NEMO_MODEL
    if not remote:
        bin_path = _resolve_nemo_bin()
        # Self-provisioning: a fresh machine or a new alias downloads its model
        # here instead of failing deep inside transcribe.
        ensure_ok, ensure_detail = ensure_model_cached(model)
        if not ensure_ok:
            raise RuntimeError(f"ASR model '{model}' unavailable: {ensure_detail}")
    wav_path = _extract_wav(media_path)
    try:
        if remote:
            print("🎙️ Transcribing via remote GPU (Colab)…", flush=True)
            payload, _elapsed = _transcribe_remote(wav_path)
        else:
            cmd = [bin_path, "transcribe", wav_path, "--model", model, "--format", "json"]
            with _ASR_GATE:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=_ASR_TIMEOUT_SECONDS)
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass

    if not remote:
        if proc.returncode != 0:
            tail = (proc.stderr or "")[-_STDERR_TAIL_CHARS:].strip()
            raise RuntimeError(f"nemo-speech transcribe failed ({proc.returncode}): {tail}")
        _require_cuda(proc.stderr)

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"nemo-speech returned unreadable JSON ({e}); stderr tail: "
            f"{(proc.stderr or '')[-_STDERR_TAIL_CHARS:].strip()}") from e

    words = []
    for w in payload.get("words") or []:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        words.append({
            "word": " " + text,
            "start": float(w["start"]),
            "end": float(w["end"]),
            "confidence": float(w.get("confidence") or 0.0),
        })
    words.sort(key=lambda w: w["start"])

    text = str(payload.get("text") or "").strip()
    if not text and words:
        text = "".join(w["word"] for w in words).strip()

    return {
        "text": text,
        "language": _detect_language(text),
        "segments": _segments_from_words(words),
    }


def _segments_from_words(words, gap_seconds=1.2, max_seconds=30.0):
    """Group the flat nemo-speech words array into transcript segments.

    The contract (and the Gemini prompt, and clip windows) read segment texts;
    nemo-speech emits one flat word list, so segments are rebuilt at speech
    pauses: an inter-word gap over gap_seconds starts a segment, and a
    pauseless speaker is hard-capped at max_seconds so chunks stay usable.
    """
    chunks = []
    current = []
    for word in words:
        if current and (
            word["start"] - current[-1]["end"] > gap_seconds
            or word["end"] - current[0]["start"] > max_seconds
        ):
            chunks.append(current)
            current = []
        current.append(word)
    if current:
        chunks.append(current)

    segments = []
    for chunk in chunks:
        segments.append({
            "start": float(chunk[0]["start"]),
            "end": float(chunk[-1]["end"]),
            "text": " ".join(w["word"].strip() for w in chunk),
            "words": chunk,
        })
    return segments


def _detect_language(text):
    """Parakeet reports no language; classify the transcribed text.

    py3langid is pure-Python and returns ISO 639-1 codes compatible with the
    codes the pipeline expects (thumbnail titles, Gemini prompts).
    """
    sample = (text or "").strip()
    if len(sample) < 20:
        return "en"
    try:
        import py3langid
        lang, _score = py3langid.classify(sample[:4000])
        return lang
    except Exception:
        return "en"


# --- public entry point -----------------------------------------------------

class NoAudioError(Exception):
    """The media has no audio track — nothing to transcribe."""


def _has_audio_stream(media_path) -> bool:
    """True if the file has at least one audio stream (ffprobe)."""
    if not os.path.exists(media_path):
        # A missing file probes the same as a streamless one; give each its own
        # error so a typo'd path doesn't read as a silent video.
        raise FileNotFoundError(f"media not found: {media_path}")
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", media_path],
            capture_output=True, text=True, timeout=60,
        )
        return bool(out.stdout.strip())
    except Exception:
        return True  # probe failed — don't block, let the backend try


def transcribe_media(media_path):
    """Transcribe on CUDA via NeMo-Speech.cpp. GPU-only, no fallback backend."""
    # Silent videos (AI-generated clips, muted screen recordings) have no audio
    # stream; every ASR backend then crashes deep inside libav with an opaque
    # "tuple index out of range". Detect it up front and fail with a clear,
    # actionable reason instead.
    if not _has_audio_stream(media_path):
        raise NoAudioError(
            "This video has no audio track. OpenShorts finds viral moments from "
            "speech, so it needs a video with audio.")

    started = time.time()
    print("🎙️ Transcribing audio…", flush=True)
    transcript = _transcribe_with_nemo(media_path)
    elapsed = int(time.time() - started)
    print(f"🎙️ Transcribing… 100% ({elapsed}s)", flush=True)
    # Self-host diagnostic (cloud users get only the curated lines above)
    print(f"🎙️ [ASR] nemo ok: lang={transcript['language']} "
          f"segments={len(transcript['segments'])} ({elapsed}s)")
    return transcript
