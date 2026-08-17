"""Step Functions handler: load — download source image, write debug frame.

Handles HEIC, JPEG, PNG. No DNG on web path.
Bypasses steps.load.run() directly to handle S3→local→S3 flow cleanly.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from handlers.common import (
    S3_BUCKET, REGION, fail_job, make_config, make_storage,
    update_step, write_thumbnail,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_UPLOAD_EXTS = [".heic", ".HEIC", ".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG"]


def handler(event: dict, context: Any) -> dict:
    """Load source image from S3, write ``debug/{stem}_01_loaded.jpg``."""
    user_hash: str = event["user_hash"]
    job_id: str = event["job_id"]
    stem: str = event["stem"]

    update_step(user_hash, job_id, "load", "Loading source image")
    storage = make_storage(user_hash)
    config = make_config(event.get("config"))

    # Locate the uploaded source file
    source_key: str | None = None
    for ext in _UPLOAD_EXTS:
        candidate = f"uploads/{stem}{ext}"
        if storage.exists(candidate):
            source_key = candidate
            break

    if source_key is None:
        err = f"No uploaded file found for stem {stem!r}"
        fail_job(user_hash, job_id, err)
        raise FileNotFoundError(err)

    # Download to /tmp so load_image() can read format metadata
    ext = Path(source_key).suffix
    tmp_path = os.path.join(tempfile.mkdtemp(), f"{stem}{ext}")
    storage.download_local(source_key, tmp_path)

    try:
        from src.preprocessing.loader import load_image
        image, metadata = load_image(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Write debug frame (full working resolution)
    debug_key = f"debug/{stem}_01_loaded.jpg"
    storage.write_image(debug_key, image, format="jpeg", quality=95)

    # Write 400px thumbnail for library card + Phase 5 step detail
    thumb_key = f"thumbnails/{stem}_01_loaded.jpg"
    write_thumbnail(storage, debug_key, thumb_key)

    update_step(
        user_hash, job_id, "load", "Loaded",
        debug_keys={"01_loaded": debug_key},
        thumbnail_keys={"01_loaded": thumb_key},
    )

    logger.info(
        "load: %s → %dx%d (%s)",
        source_key, metadata.original_size[0], metadata.original_size[1], metadata.format,
    )

    return {
        **event,
        "source_key": source_key,
        "original_width": metadata.original_size[0],
        "original_height": metadata.original_size[1],
        "source_format": metadata.format,
    }
