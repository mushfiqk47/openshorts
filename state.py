"""Mutable application state: the job store behind one shared seam.

Interface: `jobs`, `publish_jobs`, `job_queue`, `_enqueue_job`. Every route,
worker, and test crosses this seam; the dict shapes behind it are an
implementation detail. Because the dicts are module-level singletons, a
`from state import jobs` in app.py keeps `app_module.jobs` the identical
object the test suite mutates today.
"""

import asyncio
import itertools
from typing import Dict

from config import MAX_CONCURRENT_JOBS

# PriorityQueue holds (priority, seq, job_id). Lower priority dispatches first:
# pro=0, starter/creator=1, BYOK/anonymous/self-host=2. The seq counter keeps
# FIFO order within a priority and makes the tuples always comparable. With
# BILLING disabled every job enqueues at priority 2 → plain FIFO as before.
job_queue = asyncio.PriorityQueue()
_job_seq = itertools.count()
jobs: Dict[str, Dict] = {}
publish_jobs: Dict[str, Dict] = {}  # {publish_id: {status, result, error}}
# Semaphore to limit concurrency to MAX_CONCURRENT_JOBS
concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


def _enqueue_job(job_id: str, priority: int = 2):
    job_queue.put_nowait((priority, next(_job_seq), job_id))
