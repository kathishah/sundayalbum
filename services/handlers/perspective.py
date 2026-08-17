"""Step Functions handler: perspective."""
from __future__ import annotations
import logging
from typing import Any
from handlers.common import (
    fail_job, make_config, make_storage, update_step, write_thumbnail,
)
import src.steps.perspective as step

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    user_hash, job_id, stem = event["user_hash"], event["job_id"], event["stem"]
    update_step(user_hash, job_id, "perspective", "Correcting perspective")
    storage = make_storage(user_hash)
    config = make_config(event.get("config"))
    try:
        result = step.run(storage, stem, config)
    except Exception as exc:
        fail_job(user_hash, job_id, f"perspective failed: {exc}")
        raise
    debug_key = f"debug/{stem}_03_page_warped.jpg"
    thumb_key = f"thumbnails/{stem}_03_page_warped.jpg"
    write_thumbnail(storage, debug_key, thumb_key)
    update_step(
        user_hash, job_id, "perspective", "Perspective corrected",
        debug_keys={"03_page_warped": debug_key},
        thumbnail_keys={"03_page_warped": thumb_key},
    )
    logger.info("perspective: result=%s", result)
    return {**event, **result}
