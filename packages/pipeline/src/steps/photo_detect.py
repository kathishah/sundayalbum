"""Step: photo_detect — find individual photo boundaries on the page."""

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
    """Detect individual photo regions on the perspective-corrected page.

    Skips detection when the perspective step used the multi-blob path
    (photos were already extracted there).

    Reads:
    * ``debug/{stem}_03_page_warped.jpg``
    * ``debug/{stem}_03_page_detection.json``

    Writes:
    * ``debug/{stem}_04_photo_boundaries.jpg`` — detection overlay
    * ``debug/{stem}_05_photo_detections.json`` — detection results

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: Unused; present for API uniformity.

    Returns:
        Dict with keys ``photo_count`` (int), ``multi_blob`` (bool),
        ``detections`` (list of detection dicts).
    """
    from src.photo_detection.detector import detect_photos, draw_photo_detections
    from src.page_detection.detector import draw_page_detection

    # --- Forced-detections override ----------------------------------------
    # When the user has manually adjusted boundaries, the caller sets
    # config.forced_detections to a list of detection dicts.  Write them
    # directly to the JSON and return without running contour detection.
    if config.forced_detections is not None:
        # Normalise each dict: ensure required keys have defaults.
        # Accept free-form quad corners when present; derive axis-aligned
        # corners from bbox as a fallback for backward compatibility.
        forced = [
            {
                "bbox": list(d["bbox"]),
                "corners": (
                    [list(c) for c in d["corners"]]
                    if "corners" in d
                    else _corners_from_bbox(d["bbox"])
                ),
                "confidence": float(d.get("confidence", 1.0)),
                "region_type": str(d.get("region_type", "photo")),
                "orientation": str(d.get("orientation", "unknown")),
            }
            for d in config.forced_detections
        ]
        result: dict = {
            "photo_count": len(forced),
            "multi_blob": False,
            "detections": forced,
        }
        storage.write_json(f"debug/{stem}_05_photo_detections.json", result)

        # Draw overlay — only if the page image is available (may be absent when
        # running photo_detect in isolation without preceding steps)
        try:
            page_image = storage.read_image(f"debug/{stem}_03_page_warped.jpg")
            overlay = _draw_forced_boundaries(page_image, forced)
            storage.write_image(
                f"debug/{stem}_04_photo_boundaries.jpg", overlay, format="jpeg", quality=90
            )
        except Exception as exc:
            logger.debug("photo_detect: could not write overlay for forced detections: %s", exc)

        logger.info("photo_detect: using %d forced detection(s)", len(forced))
        return result

    page_detection = storage.read_json(f"debug/{stem}_03_page_detection.json")
    multi_blob: bool = len(page_detection.get("photo_quads", [])) >= 2

    if multi_blob:
        blob_count = len(page_detection["photo_quads"])
        logger.info("photo_detect: multi-blob path — %d photos already extracted", blob_count)

        # Write a placeholder boundaries image (the page_warped image)
        page_image = storage.read_image(f"debug/{stem}_03_page_warped.jpg")
        storage.write_image(
            f"debug/{stem}_04_photo_boundaries.jpg",
            page_image,
            format="jpeg",
            quality=90,
        )

        result: dict = {
            "photo_count": blob_count,
            "multi_blob": True,
            "detections": [],
        }
        storage.write_json(f"debug/{stem}_05_photo_detections.json", result)
        return result

    # --- Normal contour detection ------------------------------------------
    page_image = storage.read_image(f"debug/{stem}_03_page_warped.jpg")
    page_was_corrected: bool = not page_detection["is_full_frame"]

    detections = detect_photos(
        page_image,
        min_area_ratio=config.photo_detect_min_area_ratio,
        max_count=config.photo_detect_max_count,
        method=config.photo_detect_method,
        page_was_corrected=page_was_corrected,
    )

    overlay = draw_photo_detections(page_image, detections)
    storage.write_image(
        f"debug/{stem}_04_photo_boundaries.jpg", overlay, format="jpeg", quality=90
    )

    # Serialise detections — include quad corners alongside bbox so the
    # interactive editor can seed from them and photo_split can use them.
    det_list = [
        {
            "bbox": list(d.bbox),
            "corners": d.corners.tolist(),
            "confidence": float(d.confidence),
            "region_type": getattr(d, "region_type", "photo"),
            "orientation": getattr(d, "orientation", "unknown"),
        }
        for d in detections
    ]
    result = {
        "photo_count": len(detections),
        "multi_blob": False,
        "detections": det_list,
    }
    storage.write_json(f"debug/{stem}_05_photo_detections.json", result)

    logger.info("photo_detect: found %d photo(s)", len(detections))
    return result


def _corners_from_bbox(bbox: list) -> list[list[float]]:
    """Derive axis-aligned TL/TR/BR/BL corners from an [x1, y1, x2, y2] bbox.

    Args:
        bbox: Four-element sequence [x1, y1, x2, y2].

    Returns:
        List of four [x, y] corner points in clockwise order from top-left.
    """
    x1, y1, x2, y2 = bbox
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _draw_forced_boundaries(page_image: "np.ndarray", forced: list[dict]) -> "np.ndarray":
    """Draw coloured quad outlines for forced detections onto *page_image*.

    Uses ``corners`` (free-form quad) when present; falls back to ``bbox``
    (axis-aligned rectangle) for backward compatibility.

    Args:
        page_image: Float32 RGB [0, 1] page image.
        forced: List of detection dicts with ``bbox`` and optional ``corners``.

    Returns:
        Float32 RGB [0, 1] overlay image.
    """
    import cv2
    import numpy as np

    colours = [
        (0.95, 0.65, 0.00),  # amber
        (0.18, 0.55, 0.34),  # green
        (0.24, 0.48, 0.78),  # blue
        (0.80, 0.25, 0.25),  # red
        (0.55, 0.25, 0.78),  # purple
    ]
    overlay = (page_image * 255).astype("uint8").copy()
    for i, det in enumerate(forced):
        r, g, b = colours[i % len(colours)]
        colour_bgr = (int(b * 255), int(g * 255), int(r * 255))

        if "corners" in det and len(det["corners"]) == 4:
            pts = np.array([[int(c[0]), int(c[1])] for c in det["corners"]], dtype=np.int32)
            cv2.polylines(overlay, [pts], isClosed=True, color=colour_bgr, thickness=3)
            label_x, label_y = pts[0][0] + 6, pts[0][1] + 24
        else:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            cv2.rectangle(overlay, (x1, y1), (x2, y2), colour_bgr, 3)
            label_x, label_y = x1 + 6, y1 + 24

        label = f"Photo {i + 1} (forced)"
        cv2.putText(overlay, label, (label_x, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour_bgr, 2, cv2.LINE_AA)
    return overlay.astype("float32") / 255.0
