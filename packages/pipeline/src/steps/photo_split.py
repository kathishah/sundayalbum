"""Step: photo_split — extract individual photos from the page image."""

import logging
from typing import Optional

from src.pipeline import PipelineConfig
from src.storage.backend import StorageBackend

logger = logging.getLogger(__name__)


def run(
    storage: StorageBackend,
    stem: str,
    config: PipelineConfig,
    photo_index: Optional[int] = None,
) -> dict:
    """Extract individual photo crops from the page and write them to storage.

    For the multi-blob path: renames the already-extracted blob images
    (``debug/{stem}_03b_blob_NN_extracted.jpg``) to the standard per-photo
    key (``debug/{stem}_05_photo_NN_raw.jpg``).

    For the normal path: uses the detected bounding boxes to crop each photo
    from the page image and writes each crop.

    Falls back to writing the full page as a single photo if no detections.

    Reads:
    * ``debug/{stem}_03_page_warped.jpg``
    * ``debug/{stem}_05_photo_detections.json``
    * ``debug/{stem}_03b_blob_NN_extracted.jpg`` (multi-blob only)

    Writes:
    * ``debug/{stem}_05_photo_NN_raw.jpg`` for each photo (1-indexed)

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: Unused; present for API uniformity.

    Returns:
        Dict with ``photo_count`` (int).
    """
    from src.photo_detection.splitter import split_photos

    detection_result = storage.read_json(f"debug/{stem}_05_photo_detections.json")
    multi_blob: bool = detection_result.get("multi_blob", False)
    photo_count: int = detection_result["photo_count"]

    # --- Multi-blob: blob images already extracted by perspective step ------
    if multi_blob:
        logger.info("photo_split: multi-blob — copying %d blob images", photo_count)
        for i in range(1, photo_count + 1):
            blob_image = storage.read_image(f"debug/{stem}_03b_blob_{i:02d}_extracted.jpg")
            storage.write_image(
                f"debug/{stem}_05_photo_{i:02d}_raw.jpg",
                blob_image,
                format="jpeg",
                quality=95,
            )
        return {"photo_count": photo_count}

    # --- Normal path: split from page image --------------------------------
    page_image = storage.read_image(f"debug/{stem}_03_page_warped.jpg")

    if photo_count == 0:
        # No detections — treat entire page as one photo
        logger.info("photo_split: no detections — treating full page as single photo")
        storage.write_image(
            f"debug/{stem}_05_photo_01_raw.jpg", page_image, format="jpeg", quality=95
        )
        return {"photo_count": 1}

    # Reconstruct PhotoDetection objects from the stored detection dicts.
    # We use the stored bboxes directly (rather than re-running detect_photos)
    # so that manual boundary overrides written by photo_detect are respected.
    det_dicts = detection_result["detections"]
    detections = _detections_from_dicts(det_dicts, page_image)

    if not detections:
        logger.warning("photo_split: no valid detections in JSON — using full page")
        storage.write_image(
            f"debug/{stem}_05_photo_01_raw.jpg", page_image, format="jpeg", quality=95
        )
        return {"photo_count": 1}

    extracted = split_photos(page_image, detections)

    for i, photo in enumerate(extracted, 1):
        storage.write_image(
            f"debug/{stem}_05_photo_{i:02d}_raw.jpg",
            photo,
            format="jpeg",
            quality=95,
        )
        logger.debug(
            "photo_split: wrote photo %d (%dx%d)", i, photo.shape[1], photo.shape[0]
        )

    actual_count = len(extracted)
    logger.info("photo_split: extracted %d photo(s)", actual_count)
    return {"photo_count": actual_count}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detections_from_dicts(det_dicts: list[dict], page_image: "np.ndarray") -> list:
    """Reconstruct :class:`PhotoDetection` objects from stored detection dicts.

    Prefers the ``corners`` key (free-form quadrilateral) when present so that
    keystoned or rotated user-adjusted regions are extracted via a full
    perspective warp rather than an axis-aligned crop.  Falls back to deriving
    axis-aligned corners from ``bbox`` for backward compatibility.

    Args:
        det_dicts: List of dicts with at minimum a ``bbox`` key
                   (``[x1, y1, x2, y2]`` in pixel coordinates) and an
                   optional ``corners`` key ([[x,y] × 4, TL/TR/BR/BL order).
        page_image: The page image (used only to compute ``area_ratio``).

    Returns:
        List of :class:`PhotoDetection` objects.
    """
    import numpy as np
    from src.photo_detection.detector import PhotoDetection

    h, w = page_image.shape[:2]
    page_area = h * w
    detections = []

    for d in det_dicts:
        try:
            if "corners" in d and len(d["corners"]) == 4:
                # Free-form quad: use as-is, clamped to image bounds.
                corners = np.array(d["corners"], dtype=np.float32)
                corners[:, 0] = np.clip(corners[:, 0], 0, w)
                corners[:, 1] = np.clip(corners[:, 1], 0, h)
                # Derive a bounding bbox from the quad for area_ratio / PhotoDetection.
                x1 = int(corners[:, 0].min())
                y1 = int(corners[:, 1].min())
                x2 = int(corners[:, 0].max())
                y2 = int(corners[:, 1].max())
            else:
                # Axis-aligned bbox fallback (old format or auto-detection without corners).
                x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
                x1, x2 = max(0, x1), min(w, x2)
                y1, y2 = max(0, y1), min(h, y2)
                corners = np.array(
                    [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32
                )

            if x2 <= x1 or y2 <= y1:
                continue

            area_ratio = ((x2 - x1) * (y2 - y1)) / max(page_area, 1)
            contour = corners.reshape(-1, 1, 2).astype(np.int32)
            det = PhotoDetection(
                bbox=(x1, y1, x2, y2),
                corners=corners,
                confidence=float(d.get("confidence", 1.0)),
                orientation=str(d.get("orientation", "unknown")),
                area_ratio=area_ratio,
                contour=contour,
            )
            detections.append(det)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("photo_split: skipping malformed detection dict: %s — %s", d, exc)

    return detections
