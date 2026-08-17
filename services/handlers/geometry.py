"""Step Functions handler: geometry (per-photo, runs inside Map state)."""
from __future__ import annotations
import logging
from typing import Any
from handlers.common import (
    fail_job, make_config, make_storage, update_step, write_thumbnail,
)
import src.steps.geometry as step

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    user_hash, job_id, stem = event["user_hash"], event["job_id"], event["stem"]
    photo_index: int = int(event["photo_index"])
    update_step(user_hash, job_id, "geometry", f"Geometry correction for photo {photo_index}")
    storage = make_storage(user_hash)
    config = make_config(event.get("config"))
    try:
        result = step.run(storage, stem, config, photo_index=photo_index)
    except Exception as exc:
        fail_job(user_hash, job_id, f"geometry[{photo_index}] failed: {exc}")
        raise
    idx = f"{photo_index:02d}"
    label = f"10_photo_{idx}_geometry_final"
    debug_key = f"debug/{stem}_{label}.jpg"
    thumb_key = f"thumbnails/{stem}_{label}.jpg"
    write_thumbnail(storage, debug_key, thumb_key)
    update_step(
        user_hash, job_id, "geometry",
        f"Photo {photo_index} geometry corrected",
        debug_keys={label: debug_key},
        thumbnail_keys={label: thumb_key},
    )
    logger.info("geometry[%d]: %s", photo_index, result)
    return {**event, **result}
