"""Step Functions handler: normalize."""
from __future__ import annotations
import logging
from typing import Any
from handlers.common import (
    fail_job, make_config, make_storage, update_step, write_thumbnail,
)
import src.steps.normalize as step

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    user_hash, job_id, stem = event["user_hash"], event["job_id"], event["stem"]
    update_step(user_hash, job_id, "normalize", "Resizing image")
    storage = make_storage(user_hash)
    config = make_config(event.get("config"))
    try:
        result = step.run(storage, stem, config)
    except Exception as exc:
        fail_job(user_hash, job_id, f"normalize failed: {exc}")
        raise
    debug_key = f"debug/{stem}_02_normalized.jpg"
    thumb_key = f"thumbnails/{stem}_02_normalized.jpg"
    write_thumbnail(storage, debug_key, thumb_key)
    update_step(
        user_hash, job_id, "normalize", "Normalized",
        debug_keys={"02_normalized": debug_key},
        thumbnail_keys={"02_normalized": thumb_key},
    )
    logger.info("normalize: %dx%d (scale=%.3f)", result["width"], result["height"], result["scale_factor"])
    return {**event, **result}
