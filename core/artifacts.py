"""The on-disk artifact contract between the pipeline and the server.

main.py (run as a subprocess) WRITES these files; everything in server/
READS them through this module — the ``*_metadata.json`` discovery/load
shape, the clip file naming (canonical + derived prefixes), and the
recipe/transcript window math. One owner, so a schema change has one
place to land instead of being re-derived in every endpoint.
"""
import glob
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import recut

METADATA_SUFFIX = "_metadata.json"


def find_metadata_files(directory: str) -> List[str]:
    """Every metadata JSON in a directory, unsorted (glob order)."""
    return glob.glob(os.path.join(directory, f"*{METADATA_SUFFIX}"))


def latest_metadata(directory: str) -> Optional[str]:
    """The metadata file an endpoint should read, or None."""
    files = find_metadata_files(directory)
    return files[0] if files else None


def metadata_base_name(path: str) -> str:
    """``<base>_metadata.json`` → ``<base>``: the stem every clip filename
    is built from."""
    return os.path.basename(path)[: -len(METADATA_SUFFIX)]


def load_metadata(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metadata(path: str, data: Dict[str, Any], indent: int = 4) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)


def canonical_clip_file(output_dir, base_name, index):
    """The file to serve for clip ``index``, preferring a derived version.

    The pipeline writes the clean reframe as ``<base>_clip_<n>.mp4`` and any
    post-processing (auto-captions, /api/subtitle re-styles, and clip-editor
    recuts) as ``subtitled_<ts>_<clean>.mp4`` / ``recut_<ts>_<clean>.mp4``,
    keeping the original for re-styling. Every place that rebuilds the
    canonical name from disk — restore after a restart, the R2 upload, the
    download bundle — must therefore resolve to the newest derived file, or
    clips silently lose their captions (or their recut) on a redeploy.
    """
    clean = f"{base_name}_clip_{index + 1}.mp4"
    try:
        # subtitled_*_{clean} also matches subtitled_<ts>_recut_<ts>_{clean}
        # and subtitled_<ts>_hooked_<ts>_{clean}, i.e. captioned recuts and
        # captioned hooks; the bare recut_/hooked_/hook_ patterns cover
        # derivations that shipped uncaptioned (hook_ is the legacy manual-
        # hook prefix, kept so old jobs still resolve).
        derived = (glob.glob(os.path.join(output_dir, f"subtitled_*_{clean}"))
                   + glob.glob(os.path.join(output_dir, f"recut_*_{clean}"))
                   + glob.glob(os.path.join(output_dir, f"hooked_*_{clean}"))
                   + glob.glob(os.path.join(output_dir, f"hook_{clean}")))
    except Exception:
        derived = []
    if not derived:
        return clean
    # Highest timestamp wins — that's the most recent styling.
    return os.path.basename(max(derived, key=os.path.getmtime))


def strip_burned_captions(output_dir, filename):
    """Walk ``subtitled_<ts>_`` prefixes back to the file without burned captions.

    Returns the name unchanged when there is nothing to strip (or when the
    underlying file is gone, e.g. a library restore that only kept the current
    version).
    """
    while True:
        m = re.match(r'^subtitled_\d+_(.+)$', filename)
        if not m or not os.path.exists(os.path.join(output_dir, m.group(1))):
            return filename
        filename = m.group(1)


def strip_burned_hook(output_dir, filename):
    """Walk ``hooked_<ts>_`` (and legacy ``hook_``) prefixes back to the file
    without a burned hook. Same fail-safe contract as strip_burned_captions:
    the name is returned unchanged when there is nothing to strip or the
    underlying file is gone."""
    while True:
        m = re.match(r'^(?:hooked_\d+_|hook_)(.+)$', filename)
        if not m or not os.path.exists(os.path.join(output_dir, m.group(1))):
            return filename
        filename = m.group(1)


def clip_recipe_parts(clip):
    """(segments, canonical_range) for a clip — synthesized from the flat
    start/end for clips that were never recut."""
    recipe = clip.get('recipe') or {}
    fallback = {"start": float(clip.get('start', 0) or 0),
                "end": float(clip.get('end', 0) or 0)}
    segments = recipe.get('segments') or [dict(fallback)]
    canonical_range = recipe.get('canonical_range') or dict(fallback)
    return segments, canonical_range


def clip_window(transcript: Dict[str, Any], clip: Dict[str, Any]) -> Tuple[Dict[str, Any], float, float]:
    """(window_transcript, start, end) to caption a clip against.

    Recut clips concatenate source segments, so their caption window is NOT
    the flat start..end range — the transcript is remapped clip-relative
    (recut.virtual_transcript) and the window starts at 0. Plain clips use
    the transcript as-is with their recorded range. This is the one idiom
    that used to be re-derived in _reapply_captions, the transcript endpoint
    and /api/subtitle.
    """
    recipe_segments = (clip.get('recipe') or {}).get('segments')
    if recipe_segments:
        return (recut.virtual_transcript(transcript, recipe_segments),
                0.0, recut.total_duration(recipe_segments))
    return transcript, float(clip.get('start', 0) or 0), float(clip.get('end', 0) or 0)
