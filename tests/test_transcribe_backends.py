import json
import subprocess as real_subprocess
from types import SimpleNamespace

import pytest

import transcribe_backends as tb


def _payload(words, text="And so, my fellow Americans, ask not what your country can do for you.",
             languages=None):
    """nemo-speech --format json shape (verified against the real CLI)."""
    return {
        "file": "audio.wav",
        "text": text,
        "confidence": 1,
        "duration": words[-1]["end"] if words else 0,
        "languages": languages if languages is not None else [],
        "words": [{"word": w["word"], "start": w["start"], "end": w["end"],
                   "confidence": 1} for w in words],
    }


JFK_WORDS = [
    {"word": "And", "start": 0.24, "end": 0.56},
    {"word": "so,", "start": 0.56, "end": 1.04},
    {"word": "my", "start": 1.04, "end": 1.28},
    {"word": "fellow", "start": 1.28, "end": 1.76},
    {"word": "Americans,", "start": 1.76, "end": 3.28},
    {"word": "ask", "start": 3.28, "end": 3.92},
]

CUDA_STDERR = "[asr] model=parakeet-tdt-0.6b-v3.oss-align.q8_0 head=tdt backend=CUDA0\n"
CPU_STDERR = "[asr] model=parakeet-tdt-0.6b-v3.oss-align.q8_0 head=tdt backend=CPU0\n"


@pytest.fixture
def fake_nemo(monkeypatch, tmp_path):
    """Fake nemo-speech CLI + wav extraction, returning a canned JSON payload."""
    bin_path = tmp_path / "nemo-speech.exe"
    bin_path.write_text("")
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=json.dumps(_payload(JFK_WORDS)),
                               stderr=CUDA_STDERR)

    monkeypatch.setenv("NEMO_SPEECH_BIN", str(bin_path))
    monkeypatch.setattr(tb, "subprocess", SimpleNamespace(run=fake_run))
    monkeypatch.setattr(tb, "_extract_wav", lambda path: str(tmp_path / "fake.wav"))
    tb.reset_runtime_cache()
    yield calls
    tb.reset_runtime_cache()


# --- transcript contract ----------------------------------------------------

def test_nemo_transcript_matches_contract(fake_nemo, monkeypatch):
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")
    t = tb._transcribe_with_nemo("video.mp4")

    assert t["text"].startswith("And so, my fellow Americans")
    assert t["language"] == "en"
    # Every word carries the leading space the contract's consumers rely on.
    assert [w["word"] for w in t["segments"][0]["words"][:3]] == [" And", " so,", " my"]
    for w in t["segments"][0]["words"]:
        assert type(w["start"]) is float and type(w["end"]) is float
    # Whole transcript is JSON-serializable (metadata json.dump path).
    json.dumps(t)


def test_nemo_words_survive_merge_continuation_words(fake_nemo, monkeypatch):
    from subtitles import merge_continuation_words
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")
    t = tb._transcribe_with_nemo("video.mp4")
    for seg in t["segments"]:
        assert merge_continuation_words(seg["words"]) == seg["words"]


def test_nemo_cmd_uses_model_alias_and_json(fake_nemo, monkeypatch):
    monkeypatch.setenv("NEMO_ASR_MODEL", "parakeet-tdt")
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")
    tb._transcribe_with_nemo("video.mp4")
    cmd = fake_nemo["cmd"]
    assert cmd[1] == "transcribe"
    assert cmd[2].endswith("fake.wav")
    assert "--model" in cmd and "parakeet-tdt" in cmd
    assert "--format" in cmd and "json" in cmd


def test_empty_words_fall_back_to_joined_text(fake_nemo, monkeypatch):
    empty = _payload([], text="")
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(empty), stderr=CUDA_STDERR)

    monkeypatch.setattr(tb, "subprocess", SimpleNamespace(run=fake_run))
    t = tb._transcribe_with_nemo("video.mp4")
    assert t["text"] == ""
    assert t["segments"] == []


# --- segment reconstruction --------------------------------------------------

def test_segments_split_at_speech_gaps():
    words = [
        {"word": " a", "start": 0.0, "end": 0.5},
        {"word": " b", "start": 0.5, "end": 1.0},
        {"word": " c", "start": 3.0, "end": 3.5},  # 2s pause -> new segment
    ]
    segs = tb._segments_from_words(words)
    assert [s["start"] for s in segs] == [0.0, 3.0]
    assert segs[0]["text"] == "a b"
    assert segs[1]["words"] == [words[2]]


def test_segments_hard_cap_pauseless_speaker():
    words = [{"word": f" w{i}", "start": i * 10.0, "end": i * 10.0 + 9.0} for i in range(8)]
    segs = tb._segments_from_words(words, max_seconds=30.0)
    assert all(s["end"] - s["start"] <= 30.0 for s in segs)
    assert len(segs) == 3


def test_segments_native_floats():
    segs = tb._segments_from_words([{"word": " a", "start": 0.0, "end": 0.5}])
    assert type(segs[0]["start"]) is float and type(segs[0]["end"]) is float


# --- GPU-only enforcement ----------------------------------------------------

def test_require_cuda_accepts_cuda_backend():
    tb._require_cuda(CUDA_STDERR)


def test_require_cuda_rejects_cpu_backend():
    with pytest.raises(RuntimeError, match="GPU-only"):
        tb._require_cuda(CPU_STDERR)


def test_nemo_transcription_fails_loudly_without_cuda(fake_nemo, monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(_payload(JFK_WORDS)),
                               stderr=CPU_STDERR)

    monkeypatch.setattr(tb, "subprocess", SimpleNamespace(run=fake_run))
    with pytest.raises(RuntimeError, match="no CUDA backend"):
        tb._transcribe_with_nemo("video.mp4")


def test_nemo_nonzero_exit_raises_with_stderr_tail(fake_nemo, monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="ggml_backend_alloc: OOM")

    monkeypatch.setattr(tb, "subprocess", SimpleNamespace(run=fake_run))
    with pytest.raises(RuntimeError, match="OOM"):
        tb._transcribe_with_nemo("video.mp4")


def test_nemo_unreadable_json_raises(fake_nemo, monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="not json", stderr=CUDA_STDERR)

    monkeypatch.setattr(tb, "subprocess", SimpleNamespace(run=fake_run))
    with pytest.raises(RuntimeError, match="unreadable JSON"):
        tb._transcribe_with_nemo("video.mp4")


# --- remote Colab mode -------------------------------------------------------

def test_remote_success_builds_contract(fake_nemo, monkeypatch):
    payload = {"text": "hello there", "confidence": 1, "duration": 2.0,
               "languages": [], "words": [{"word": "hello", "start": 0.0, "end": 0.5},
                                          {"word": "there", "start": 0.5, "end": 1.0}],
               "backend": "CUDA0"}
    calls = []
    monkeypatch.setattr(tb, "_transcribe_remote", lambda wav: (calls.append(wav) or (payload, 1.2)))
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")
    monkeypatch.setenv("NEMO_ASR_URL", "https://tunnel.example")
    t = tb._transcribe_with_nemo("video.mp4")
    assert calls, "remote round-trip never ran"
    assert t["language"] == "en"
    assert [w["word"] for w in t["segments"][0]["words"][:1]] == [" hello"]


def test_remote_failure_falls_back_to_local_gpu(fake_nemo, monkeypatch):
    from types import SimpleNamespace as NS
    monkeypatch.setattr(tb, "_transcribe_remote",
                        lambda wav: (_ for _ in ()).throw(RuntimeError("tunnel died")))
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")

    def fake_run(cmd, **kwargs):
        if "pull" in cmd:
            return NS(returncode=0, stdout="cached", stderr="")
        return NS(returncode=0, stdout=json.dumps(_payload(JFK_WORDS)), stderr=CUDA_STDERR)

    monkeypatch.setattr(tb, "subprocess", SimpleNamespace(run=fake_run))
    monkeypatch.setenv("NEMO_ASR_URL", "https://tunnel.example")
    t = tb._transcribe_with_nemo("video.mp4")
    assert t["text"].startswith("And so, my fellow Americans")


# --- live concurrency gate ---------------------------------------------------

def test_env_semaphore_sizes_from_env(monkeypatch):
    monkeypatch.setenv("ASR_GPU_CONCURRENCY", "2")
    gate = tb._EnvSemaphore("ASR_GPU_CONCURRENCY")
    with gate:  # size-2 gate admits a second holder
        pass
    assert gate._value == 2


def test_env_semaphore_picks_up_live_change(monkeypatch):
    monkeypatch.setenv("ASR_GPU_CONCURRENCY", "1")
    gate = tb._EnvSemaphore("ASR_GPU_CONCURRENCY")
    with gate:
        first = gate._current()
    monkeypatch.setenv("ASR_GPU_CONCURRENCY", "3")
    second = gate._current()
    assert second is not first and gate._value == 3


def test_env_semaphore_invalid_value_falls_back_to_one(monkeypatch):
    monkeypatch.setenv("ASR_GPU_CONCURRENCY", "not-a-number")
    gate = tb._EnvSemaphore("ASR_GPU_CONCURRENCY")
    assert gate._current() is gate._gate and gate._value == 1
    monkeypatch.setenv("ASR_GPU_CONCURRENCY", "0")
    assert gate._value == 1


# --- CLI resolution ----------------------------------------------------------

def test_missing_cli_raises_with_install_hint(monkeypatch):
    monkeypatch.delenv("NEMO_SPEECH_BIN", raising=False)
    monkeypatch.setattr(tb.shutil, "which", lambda name: None)
    monkeypatch.setattr(tb.os.path, "isfile", lambda path: False)
    tb.reset_runtime_cache()
    try:
        with pytest.raises(RuntimeError, match="nemo-speech CLI not found"):
            tb._resolve_nemo_bin()
    finally:
        tb.reset_runtime_cache()


def test_cli_resolution_is_memoized(monkeypatch, tmp_path):
    bin_path = tmp_path / "nemo-speech.exe"
    bin_path.write_text("")
    monkeypatch.setenv("NEMO_SPEECH_BIN", str(bin_path))
    tb.reset_runtime_cache()
    first = tb._resolve_nemo_bin()
    second = tb._resolve_nemo_bin()
    assert first == second == str(bin_path)
    tb.reset_runtime_cache()


# --- public entry point ------------------------------------------------------

def test_transcribe_media_raises_on_silent_video(monkeypatch):
    monkeypatch.setattr(tb, "_has_audio_stream", lambda path: False)
    with pytest.raises(tb.NoAudioError):
        tb.transcribe_media("silent.mp4")


def test_transcribe_media_goes_through_nemo(fake_nemo, monkeypatch):
    monkeypatch.setattr(tb, "_has_audio_stream", lambda path: True)
    monkeypatch.setattr(tb, "_detect_language", lambda text: "en")
    t = tb.transcribe_media("video.mp4")
    assert t["language"] == "en"
    assert "cmd" in fake_nemo  # the CLI was actually invoked


def test_detect_language_defaults_to_en_for_short_text():
    assert tb._detect_language("hi") == "en"
