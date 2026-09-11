"""Scene detection engines for the reframe pipeline.

Primary engine: TransNetV2, a small neural shot-boundary detector that is
markedly more accurate than threshold-based detection (handles fast camera
motion, flashes and gradual transitions such as fades/dissolves). Runs on
48x27 frames, faster than realtime even on CPU.

Fallback/legacy engine: PySceneDetect ContentDetector, byte-for-byte the
pre-existing behavior. Any TransNetV2 failure (missing package, corrupt
weights, decode error) falls back automatically so a scene-detection edge
case can never kill a job.

Environment variables:
  SCENE_ENGINE          "transnetv2" (default) | "pyscenedetect" (legacy)
  SCENE_MIN_SEC         minimum scene length in seconds; shorter scenes are
                        merged into a neighbor (default 0.4, TransNetV2 path
                        only — the legacy path stays untouched)
  TRANSNETV2_THRESHOLD  shot-boundary probability threshold (default 0.5)
  TRANSNETV2_DEVICE     torch device: "auto" (default) | "cpu" | "cuda" | "mps"
                        "auto" uses CUDA when torch actually has it, else CPU; an
                        explicit "cuda" on a CPU-only torch falls back to CPU
                        with an info log (no scary warning)
"""

import os
import subprocess
import sys
import threading

# Windows cp1252 can't encode emojis; force utf-8 for prints
for _s in ("stdout", "stderr"):
    _st = getattr(sys, _s, None)
    if _st and hasattr(_st, "reconfigure"):
        try:
            _st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import cv2
import numpy as np
from scenedetect import open_video, SceneManager, FrameTimecode
from scenedetect.detectors import ContentDetector

# TransNetV2 input size (width x height), fixed by the trained model.
_TN2_W, _TN2_H = 48, 27

# One shared model instance; clips can process in parallel (CLIP_WORKERS) so
# inference is serialized like the other detectors in main.py.
_TN2_LOCK = threading.Lock()
_tn2_model = None


def _cuda_available():
    """True when torch can actually use CUDA. CPU-only torch builds lack
    CUDA support entirely - either way this is False, never an exception."""
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _mps_available():
    try:
        import torch
        mps = getattr(getattr(torch, "backends", None), "mps", None)
        return bool(mps and mps.is_available())
    except Exception:
        return False


def _resolve_tn2_device(requested):
    """Map TRANSNETV2_DEVICE to an explicit device the lib can construct.

    Never returns "auto": TransNetV2 auto handling assumes a CUDA-built
    torch and raises on CPU-only installs. Resolving here keeps CPU hosts
    on a quiet CPU path instead of a fallback warning.
    """
    req = (requested or "auto").strip().lower()
    if req in ("", "auto"):
        if _cuda_available():
            return "cuda"
        if _mps_available():
            return "mps"
        return "cpu"
    if req in ("cuda", "0", "gpu"):
        return "cuda" if _cuda_available() else "cpu"
    if req == "mps":
        return "mps" if _mps_available() else "cpu"
    return "cpu"


def detect_scenes(video_path):
    """Detect scenes. Returns (scene_list, fps) where scene_list is a list of
    (FrameTimecode, FrameTimecode) pairs — the same contract PySceneDetect's
    SceneManager.get_scene_list() has always given callers."""
    engine = os.environ.get("SCENE_ENGINE", "transnetv2").strip().lower()
    if engine != "pyscenedetect":
        try:
            return _detect_transnetv2(video_path)
        except Exception as e:
            msg = str(e).lower()
            if "cuda" in msg or "cublas" in msg or "nvrtc" in msg or "mps" in msg:
                print(f"   [TransNetV2] GPU unavailable "
                      f"({type(e).__name__}: {e}) — using PySceneDetect on CPU")
            else:
                print(f"   ⚠️ TransNetV2 scene detection failed "
                      f"({type(e).__name__}: {e}) — falling back to PySceneDetect")
    return _detect_pyscenedetect(video_path)


# --- legacy engine ----------------------------------------------------------

def _detect_pyscenedetect(video_path):
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video=video)
    scene_list = scene_manager.get_scene_list()
    fps = video.frame_rate
    return scene_list, fps


# --- TransNetV2 engine ------------------------------------------------------

def _get_tn2_model():
    global _tn2_model
    if _tn2_model is None:
        from transnetv2_pytorch import TransNetV2
        requested = os.environ.get("TRANSNETV2_DEVICE", "auto")
        device = _resolve_tn2_device(requested)
        if (requested or "auto").strip().lower() in ("cuda", "0", "gpu") and device == "cpu":
            print("   [TransNetV2] TRANSNETV2_DEVICE=cuda requested but CUDA "
                  "is not available (CPU-only torch?) — using CPU, which is "
                  "realtime for 48x27 frames")
        model = TransNetV2(device=device)
        model.eval()
        _tn2_model = model
    return _tn2_model


def _extract_frames_small(video_path):
    """Decode the whole clip as 48x27 RGB frames via ffmpeg (~4KB/frame)."""
    cmd = [
        "ffmpeg", "-nostdin", "-i", video_path,
        "-vf", f"scale={_TN2_W}:{_TN2_H}",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, check=True, timeout=900)
    frame_bytes = _TN2_H * _TN2_W * 3
    n = len(proc.stdout) // frame_bytes
    if n == 0:
        raise RuntimeError("ffmpeg produced no frames")
    return np.frombuffer(proc.stdout[:n * frame_bytes],
                         dtype=np.uint8).copy().reshape(n, _TN2_H, _TN2_W, 3)


def _detect_transnetv2(video_path):
    import torch

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    frames = _extract_frames_small(video_path)
    model = _get_tn2_model()
    threshold = float(os.environ.get("TRANSNETV2_THRESHOLD", "0.5"))

    with _TN2_LOCK, torch.no_grad():
        tensor = torch.from_numpy(np.ascontiguousarray(frames)).to(model.device)
        single_frame_pred, _ = model.predict_frames(tensor, quiet=True)

    # predictions_to_scenes returns [[start, end], ...] with INCLUSIVE ends;
    # downstream expects PySceneDetect's exclusive ends.
    raw = model.predictions_to_scenes(single_frame_pred.numpy(), threshold=threshold)
    bounds = [(int(s), int(e) + 1) for s, e in raw]

    # cv2's frame count can differ by a few frames from what ffmpeg decodes;
    # downstream loops run to the decoder's count, so cover the gap.
    if total_frames > bounds[-1][1]:
        bounds[-1] = (bounds[-1][0], total_frames)

    min_sec = float(os.environ.get("SCENE_MIN_SEC", "0.4"))
    bounds = _merge_short_scenes(bounds, fps, min_sec)

    scene_list = [(FrameTimecode(s, fps), FrameTimecode(e, fps))
                  for s, e in bounds]
    print(f"   🎬 Scene engine: TransNetV2 — {len(scene_list)} scenes")
    return scene_list, fps


def _merge_short_scenes(bounds, fps, min_sec):
    """Absorb scenes shorter than min_sec into a neighbor. Ultra-short scenes
    cause camera-snap bursts and starve the per-scene strategy sampling."""
    if len(bounds) <= 1 or min_sec <= 0:
        return bounds
    min_frames = max(1, int(round(min_sec * float(fps))))

    merged = []
    for s, e in bounds:
        if merged and (e - s) < min_frames:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    # The first scene can still be short — fold it into the one after it.
    if len(merged) > 1 and (merged[0][1] - merged[0][0]) < min_frames:
        merged[1] = (merged[0][0], merged[1][1])
        merged.pop(0)
    return merged
