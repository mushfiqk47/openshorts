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
"""

import os
import subprocess
import threading

import cv2
import numpy as np
from tqdm import tqdm

from tracking import detect_face_candidates
from scenedetect import open_video, SceneManager, FrameTimecode
from scenedetect.detectors import ContentDetector

# TransNetV2 input size (width x height), fixed by the trained model.
_TN2_W, _TN2_H = 48, 27

# One shared model instance; clips can process in parallel (CLIP_WORKERS) so
# inference is serialized like the other detectors in main.py.
_TN2_LOCK = threading.Lock()
_tn2_model = None


def detect_scenes(video_path):
    """Detect scenes. Returns (scene_list, fps) where scene_list is a list of
    (FrameTimecode, FrameTimecode) pairs — the same contract PySceneDetect's
    SceneManager.get_scene_list() has always given callers."""
    engine = os.environ.get("SCENE_ENGINE", "transnetv2").strip().lower()
    if engine != "pyscenedetect":
        try:
            return _detect_transnetv2(video_path)
        except Exception as e:
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
        device = os.environ.get("TRANSNETV2_DEVICE", "auto")
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
                         dtype=np.uint8).reshape(n, _TN2_H, _TN2_W, 3)


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

def analyze_scenes_strategy(video_path, scenes):
    """
    Analyzes each scene to determine if it should be TRACK (Single person) or GENERAL (Group/Wide).
    Returns list of strategies corresponding to scenes.
    """
    cap = cv2.VideoCapture(video_path)
    strategies = []

    if not cap.isOpened():
        return ['TRACK'] * len(scenes)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    for start, end in tqdm(scenes, desc="   Analyzing Scenes"):
        s_f, e_f = start.get_frames(), end.get_frames()
        # Sample 5 frames spread across the scene, clamped inside it (the old
        # start+5/end-5 samples landed outside scenes shorter than ~10 frames).
        margin = min(2, max(0, (e_f - s_f - 1) // 2))
        frames_to_check = sorted(set(
            int(round(f)) for f in np.linspace(s_f + margin, e_f - 1 - margin, 5)
        ))

        face_counts = []
        for f_idx in frames_to_check:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret: continue

            # Near-black frames (fades, cut-to-black) carry no faces and used
            # to drag single-person scenes into GENERAL. Skip them.
            if frame.mean() < 16:
                continue

            # Detect faces
            candidates = detect_face_candidates(frame)
            face_counts.append(len(candidates))

        # Decision Logic
        if not face_counts:
            avg_faces = 0
        else:
            avg_faces = sum(face_counts) / len(face_counts)

        # Strategy:
        # 0 faces -> GENERAL (Landscape/B-roll)
        # 1 face -> TRACK
        # > 1.2 faces -> GENERAL (Group)

        if avg_faces > 1.2 or avg_faces < 0.5:
            strategies.append('GENERAL')
        else:
            strategies.append('TRACK')

    cap.release()

    # Hysteresis: a short scene whose two neighbors agree on the opposite
    # strategy is almost always a sampling miss (profile face, insert shot).
    # Each TRACK<->GENERAL flip is a full on-screen layout change, so flapping
    # is worse than an occasional wrong-but-stable choice.
    max_flip_frames = int(2.0 * fps)
    for i in range(1, len(strategies) - 1):
        dur = scenes[i][1].get_frames() - scenes[i][0].get_frames()
        if (dur < max_flip_frames
                and strategies[i - 1] == strategies[i + 1] != strategies[i]):
            strategies[i] = strategies[i - 1]

    return strategies
