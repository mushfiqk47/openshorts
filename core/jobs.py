"""The in-memory job record contract.

``server.state.jobs`` maps job_id → Job. The pipeline subprocess never sees
this dict — it communicates through the artifact files (core/artifacts.py)
and its stdout — so this shape is owned by the server alone. ``job_id`` is
the key, not a field. Recovered jobs (server/jobs._recover_jobs_from_disk)
and resumed jobs carry a subset; ``total_seconds=False`` fields are optional.
"""
from typing import Any, Dict, List, Optional, TypedDict


class Job(TypedDict, total=False):
    # lifecycle
    status: str            # queued | processing | completed | failed
    logs: List[str]
    cmd: List[str]         # the subprocess argv (["python", "-u", "main.py", ...])
    env: Dict[str, str]    # the child environment (never persisted — see resume manifest)
    output_dir: str        # state.OUTPUT_DIR / job_id
    # metering / multi-tenant (managed jobs only)
    user_id: Optional[Any]
    user_plan: Optional[str]
    reservation_id: Optional[str]
    # webhook callback
    webhook_url: Optional[str]
    webhook_secret: Optional[str]
    webhook_sent: bool
    base_url: Optional[str]        # absolute-URL base for webhook payloads
    watermark: bool
    # legal attestation captured at submit
    attestation: Dict[str, Any]
    # results / bookkeeping
    result: Dict[str, Any]         # {"clips": [...], "cost_analysis": ...}
    proxy_bytes: int
    email_sent: bool
    url: Optional[str]
