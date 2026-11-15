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


def _transcribe_with_nemo(media_path):
    bin_path = _resolve_nemo_bin()
    model = os.environ.get("NEMO_ASR_MODEL", "").strip() or DEFAULT_NEMO_MODEL
    wav_path = _extract_wav(media_path)
    try:
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
