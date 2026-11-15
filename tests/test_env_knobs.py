"""Settings knobs must be live: MAX_FILE_SIZE_MB and MAX_CONCURRENT_JOBS are
writable through /api/env, so both must be honored without a restart (the old
placebo-knob bug: one never read env at all, the other froze its semaphore at
import time)."""

import app as app_module


def test_max_file_size_mb_reads_env_live(monkeypatch):
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "4096")
    assert app_module._max_file_size_mb() == 4096
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "not-an-int")
    assert app_module._max_file_size_mb() == 2048  # default on garbage
    monkeypatch.delenv("MAX_FILE_SIZE_MB", raising=False)
    assert app_module._max_file_size_mb() == 2048


def test_concurrency_semaphore_swaps_on_live_change(monkeypatch):
    original = app_module.MAX_CONCURRENT_JOBS
    original_sem = app_module.concurrency_semaphore
    try:
        monkeypatch.setenv("MAX_CONCURRENT_JOBS", str(original + 2))
        app_module._refresh_concurrency_semaphore()
        assert app_module.concurrency_semaphore is not original_sem
        assert app_module._concurrency_capacity == original + 2
        # Same value again → no further swap
        current = app_module.concurrency_semaphore
        app_module._refresh_concurrency_semaphore()
        assert app_module.concurrency_semaphore is current
    finally:
        monkeypatch.delenv("MAX_CONCURRENT_JOBS", raising=False)
        app_module.concurrency_semaphore = original_sem
        app_module._concurrency_capacity = original
