"""Step Functions handler: finalize — collect per-photo results, mark job complete."""
from __future__ import annotations
import logging
import time
from typing import Any
from handlers.common import fail_job, finalize_job, update_step

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """Collect output_keys from Map results and mark DynamoDB job as complete.

    Expected event shape (from Step Functions after Map state):
    {
        "user_hash": "...",
        "job_id": "...",
        "stem": "...",
        "start_time": <unix float>,
        "photo_results": [
            {"photo_index": 1, "output_key": "output/SundayAlbum_..._Photo01.jpg", ...},
            {"photo_index": 2, "output_key": "output/SundayAlbum_..._Photo02.jpg", ...},
        ]
    }
    """
    user_hash: str = event["user_hash"]
    job_id: str = event["job_id"]
    photo_results: list[dict] = event.get("photo_results", [])
    start_time: float = float(event.get("start_time", time.time()))

    # Sort by photo_index to ensure deterministic ordering
    photo_results_sorted = sorted(photo_results, key=lambda r: int(r.get("photo_index", 0)))
    output_keys = [r["output_key"] for r in photo_results_sorted if "output_key" in r]

    if not output_keys:
        msg = "No output keys returned from photo processing Map state"
        logger.error(msg)
        fail_job(user_hash, job_id, msg)
        raise RuntimeError(msg)

    processing_time = time.time() - start_time
    finalize_job(user_hash, job_id, output_keys, processing_time=processing_time)

    logger.info(
        "finalize: job %s complete — %d output(s) in %.1fs",
        job_id, len(output_keys), processing_time,
    )
    return {
        "job_id": job_id,
        "status": "complete",
        "photo_count": len(output_keys),
        "output_keys": output_keys,
        "processing_time": processing_time,
    }
