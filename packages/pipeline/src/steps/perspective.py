"""Step: perspective — apply homographic warp from page-detection result."""

import logging
from typing import Optional

import numpy as np

from src.pipeline import PipelineConfig
from src.storage.backend import StorageBackend

logger = logging.getLogger(__name__)


def run(
    storage: StorageBackend,
    stem: str,
    config: PipelineConfig,
    photo_index: Optional[int] = None,
) -> dict:
    """Apply perspective correction to the normalised image.

    Reads:
    * ``debug/{stem}_02_normalized.jpg``
    * ``debug/{stem}_03_page_detection.json``

    Writes:
    * ``debug/{stem}_03_page_warped.jpg`` — full-page corrected image
      (or a copy of normalised if full-frame / multi-blob)
    * ``debug/{stem}_03b_blob_NN_extracted.jpg`` — one per blob
      (multi-blob case only)

    The ``multi_blob`` flag in the returned dict tells downstream steps
    (photo_detect / photo_split) that photos were already extracted here.

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: Unused; present for API uniformity.

    Returns:
        Dict with keys ``warped`` (bool), ``multi_blob`` (bool),
        ``blob_count`` (int, 0 unless multi-blob).
    """
    from src.page_detection.perspective import correct_perspective

    image = storage.read_image(f"debug/{stem}_02_normalized.jpg")
    detection = storage.read_json(f"debug/{stem}_03_page_detection.json")

    corners = np.array(detection["corners"], dtype=np.float32)
    photo_quads = [np.array(q, dtype=np.float32) for q in detection.get("photo_quads", [])]
    is_full_frame: bool = detection["is_full_frame"]

    # --- Multi-blob path ---------------------------------------------------
    # Two or more foreground blobs detected by GrabCut: each blob is a
    # separate physical print.  Perspective-correct each blob independently
    # from the pre-warp (normalised) image and write them as extracted photos.
    if len(photo_quads) >= 2:
        logger.info("perspective: multi-blob path — %d blobs", len(photo_quads))
        for blob_idx, quad in enumerate(photo_quads, 1):
            blob_photo = correct_perspective(image, quad)
            storage.write_image(
                f"debug/{stem}_03b_blob_{blob_idx:02d}_extracted.jpg",
                blob_photo,
                format="jpeg",
                quality=95,
            )

        # Write the normalised image as the "warped" image so downstream
        # steps that always read page_warped.jpg have something to read.
        storage.write_image(
            f"debug/{stem}_03_page_warped.jpg", image, format="jpeg", quality=95
        )
        return {"warped": False, "multi_blob": True, "blob_count": len(photo_quads)}

    # --- Full-frame path ---------------------------------------------------
    if is_full_frame:
        logger.info("perspective: full-frame — no warp applied")
        storage.write_image(
            f"debug/{stem}_03_page_warped.jpg", image, format="jpeg", quality=95
        )
        return {"warped": False, "multi_blob": False, "blob_count": 0}

    # --- Single-quad path --------------------------------------------------
    warped = correct_perspective(image, corners)
    storage.write_image(
        f"debug/{stem}_03_page_warped.jpg", warped, format="jpeg", quality=95
    )
    logger.info(
        "perspective: warped %dx%d → %dx%d",
        image.shape[1], image.shape[0],
        warped.shape[1], warped.shape[0],
    )
    return {"warped": True, "multi_blob": False, "blob_count": 0}
