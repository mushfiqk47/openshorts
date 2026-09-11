"""User-supplied transcripts: TXT / MD / SRT / VTT / JSON -> pipeline contract.

The pipeline (clip_selection, subtitles, recut) only ever reads one shape:

    {"language": str,
     "segments": [{"start": float, "end": float, "text": str,
                   "words": [{"word": str, "start": float, "end": float}]}]}

Word dicts carry a LEADING SPACE on true word starts (Whisper convention);
continuation fragments without it get glued together downstream, so every
word emitted here starts with exactly one space.

Timestamp strategy (no audio alignment on purpose — that would need Whisper,
which this module exists to avoid):
  - SRT / VTT: cue-level timestamps are real. Words inside a cue are spread
    evenly across the cue span. Error <= cue_duration / n_words (~0.3s).
  - TXT / MD: no timestamps at all. Words are spread evenly across the full
    video duration, grouped into ~8s segments so clip windows still work.
    Error grows on uneven speech; 15-60s clip boundaries stay usable.
  - JSON: already in the contract shape (old --transcript files). Used as-is
    after validation.

Stdlib only, so main.py stays runnable without heavy deps.
"""
import json
import os
import re

_WORD_RE = re.compile(r"\S+")
_SRT_TS_RE = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)
_VTT_TS_RE = re.compile(
    r"(?:(\d+):)?(\d+):(\d+)\.(\d+)\s*-->\s*(?:(\d+):)?(\d+):(\d+)\.(\d+)"
)


def _ts_to_seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _spread_words(text, start, end):
    """Split [start, end] across the words in text, proportional to length.

    Even splitting gives "a" the same duration as "assessment", so the
    karaoke highlight holds short words too long and cuts long ones early.
    Weighting by character count (with a floor of 2 so single letters stay
    visible) keeps the total span identical while tracking speech rhythm."""
    tokens = _WORD_RE.findall(text)
    if not tokens:
        return []
    span = max(float(end) - float(start), 0.0)
    weights = [max(len(t), 2) for t in tokens]
    total = sum(weights)
    out = []
    cursor = float(start)
    for tok, w in zip(tokens, weights):
        share = span * w / total if span > 0 and total > 0 else 0.0
        ws = cursor
        we = cursor + share if span > 0 else float(start)
        out.append({"word": " " + tok, "start": round(ws, 3), "end": round(we, 3)})
        cursor += share
    if out:
        out[-1]["end"] = round(float(end), 3)  # absorb rounding drift
    return out


def _segments_from_words(all_words, duration, seg_len=8.0):
    """Group a flat word list into ~seg_len-second segments."""
    segments = []
    if not all_words:
        return segments
    chunk, chunk_start = [], None
    for w in all_words:
        if chunk_start is None:
            chunk_start = w["start"]
        chunk.append(w)
        if w["end"] - chunk_start >= seg_len:
            segments.append({
                "start": round(chunk[0]["start"], 3),
                "end": round(chunk[-1]["end"], 3),
                "text": "".join(x["word"] for x in chunk).strip(),
                "words": chunk,
            })
            chunk, chunk_start = [], None
    if chunk:
        segments.append({
            "start": round(chunk[0]["start"], 3),
            "end": round(min(chunk[-1]["end"], duration), 3),
            "text": "".join(x["word"] for x in chunk).strip(),
            "words": chunk,
        })
    return segments


def parse_srt(text):
    """Parse SRT cues -> (cue_start, cue_end, cue_text) list."""
    cues = []
    # Split on blank lines; each block is index / timestamps / text...
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        # Timestamp line is lines[0] or lines[1] (index line optional).
        ts_line = next((ln for ln in lines[:2] if "-->" in ln), None)
        if not ts_line:
            continue
        m = _SRT_TS_RE.search(ts_line)
        if not m:
            continue
        start = _ts_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _ts_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        cue_text = " ".join(lines[lines.index(ts_line) + 1:])
        # Strip SRT tags (<i>, <b>, {an8}, ...) and music notes.
        cue_text = re.sub(r"<[^>]+>", "", cue_text)
        cue_text = re.sub(r"\{[^}]*\}", "", cue_text).strip()
        if cue_text and end > start:
            cues.append((start, end, cue_text))
    return cues


def parse_vtt(text):
    """Parse WebVTT cues -> (cue_start, cue_end, cue_text) list."""
    cues = []
    # Drop header, NOTE/STYLE/REGION blocks.
    body = re.sub(r"^WEBVTT[^\n]*\n", "", text, count=1)
    body = re.sub(r"(?m)^(NOTE|STYLE|REGION)( .*)?(\n.*)*?(?=\n\s*\n|\Z)", "", body)
    for block in re.split(r"\r?\n\s*\r?\n", body.strip()):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue
        ts_idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if ts_idx is None:
            continue
        m = _VTT_TS_RE.search(lines[ts_idx])
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = m.groups()
        start = _ts_to_seconds(h1 or 0, m1, s1, (ms1 + "000")[:3])
        end = _ts_to_seconds(h2 or 0, m2, s2, (ms2 + "000")[:3])
        cue_text = " ".join(lines[ts_idx + 1:])
        cue_text = re.sub(r"<[^>]+>", "", cue_text).strip()
        if cue_text and end > start:
            cues.append((start, end, cue_text))
    return cues


def strip_markdown(text):
    """Remove MD syntax but keep the spoken words in order."""
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)          # headings
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links/images
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)     # bold
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)        # italic
    text = re.sub(r"`([^`]*)`", r"\1", text)            # code
    text = re.sub(r"(?m)^\s*([-*+]|\d+[.)])\s+", "", text)  # lists
    text = re.sub(r"(?m)^\s*>\s?", "", text)            # quotes
    text = re.sub(r"(?m)^\s*(-{3,}|_{3,}|\*{3,})\s*$", "", text)  # rules
    return text


def _validate_contract(data):
    segs = data.get("segments")
    if not isinstance(segs, list) or not segs:
        raise ValueError("transcript has no segments")
    for s in segs:
        words = s.get("words")
        if not isinstance(words, list) or not words:
            raise ValueError("a segment has no words")
        for w in words:
            if "word" not in w or "start" not in w or "end" not in w:
                raise ValueError("a word is missing word/start/end")
    data["language"] = str(data.get("language") or "en")
    return data


def load_transcript(path, duration):
    """Load any supported transcript file into the pipeline contract.

    Args:
        path: .txt / .md / .srt / .vtt / .json file.
        duration: source video length in seconds (for plain-text spreading).

    Raises:
        FileNotFoundError, ValueError with a human-readable reason.
    """
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            f"Transcript not found: {path}\n"
            "Pass --transcript video.srt (or .vtt / .txt / .md / .json).")
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    if not raw.strip():
        raise ValueError(f"Transcript is empty: {path}")

    if ext == ".json":
        try:
            return _validate_contract(json.loads(raw))
        except json.JSONDecodeError as e:
            raise ValueError(f"Transcript JSON is invalid: {e}")

    if ext in (".srt", ".vtt"):
        cues = parse_srt(raw) if ext == ".srt" else parse_vtt(raw)
        if not cues:
            raise ValueError(
                f"No usable cues found in {path} "
                "(timestamps like 00:00:01,000 --> 00:00:04,000 required).")
        segments = []
        for start, end, cue_text in cues:
            words = _spread_words(cue_text, start, end)
            if words:
                segments.append({"start": round(start, 3), "end": round(end, 3),
                                 "text": cue_text.strip(), "words": words})
        return {"language": "en", "segments": segments}

    if ext in (".txt", ".md", ".markdown"):
        text = strip_markdown(raw) if ext in (".md", ".markdown") else raw
        # Collapse stage directions like [Music] / (laughs) — not speech.
        text = re.sub(r"\[[^\]]*\]", " ", text)
        text = re.sub(r"\([^)]{0,60}\)", " ", text)
        tokens = _WORD_RE.findall(text)
        if not tokens:
            raise ValueError(f"No words found in {path}")
        if duration <= 0:
            raise ValueError("Cannot spread plain text without video duration.")
        step = duration / len(tokens)
        all_words = [{"word": " " + t,
                      "start": round(i * step, 3),
                      "end": round((i + 1) * step, 3)}
                     for i, t in enumerate(tokens)]
        all_words[-1]["end"] = round(duration, 3)
        text_out = " ".join(tokens)
        return {"text": text_out, "language": "en",
                "segments": _segments_from_words(all_words, duration)}

    raise ValueError(
        f"Unsupported transcript type '{ext}': use .srt, .vtt, .txt, .md or .json.")
