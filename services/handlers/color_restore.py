"""Step Functions handler: color_restore (per-photo, runs inside Map state)."""
from __future__ import annotations
import logging
from typing import Any
from handlers.common import (
    fail_job, get_existing_output_key, make_config, make_storage,
    skip_this_photo, update_step, write_thumbnail,
)
import src.steps.color_restore as step

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    user_hash, job_id, stem = event["user_hash"], event["job_id"], event["stem"]
    photo_index: int = int(event["photo_index"])

    if skip_this_photo(event):
        logger.info("color_restore[%d]: skipping (start_from=%s)", photo_index, event.get("start_from"))
        idx = f"{photo_index:02d}"
        output_key = (
            get_existing_output_key(user_hash, job_id, photo_index)
            or f"output/SundayAlbum_{stem}_Photo{idx}.jpg"
        )
        return {
            "photo_index": photo_index,
            "output_key": output_key,
            "user_hash": user_hash,
            "job_id": job_id,
            "stem": stem,
        }

    update_step(user_hash, job_id, "color_restore", f"Restoring color for photo {photo_index}")
    storage = make_storage(user_hash)
    config = make_config(event.get("config"))
    try:
        result = step.run(storage, stem, config, photo_index=photo_index)
    except Exception as exc:
        fail_job(user_hash, job_id, f"color_restore[{photo_index}] failed: {exc}")
        raise
    idx = f"{photo_index:02d}"
    label = f"14_photo_{idx}_enhanced"
    debug_key = f"debug/{stem}_{label}.jpg"
    thumb_key = f"thumbnails/{stem}_{label}.jpg"
    write_thumbnail(storage, debug_key, thumb_key)
    update_step(
        user_hash, job_id, "color_restore",
        f"Photo {photo_index} complete",
        debug_keys={label: debug_key},
        thumbnail_keys={label: thumb_key},
    )
    logger.info("color_restore[%d]: output=%s", photo_index, result.get("output_key"))
    output_key = result.get("output_key", f"output/SundayAlbum_{stem}_Photo{idx}.jpg")
    # Return only what finalize needs (keep event small)
    return {
        "photo_index": photo_index,
        "output_key": output_key,
        "user_hash": user_hash,
        "job_id": job_id,
        "stem": stem,
    }
