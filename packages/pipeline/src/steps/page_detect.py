"""Step: page_detect — detect album page boundary with GrabCut segmentation."""

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
    """Detect the album page boundary quadrilateral.

    Reads ``debug/{stem}_02_normalized.jpg``.
    Writes:
    * ``debug/{stem}_02_page_detected.jpg`` — overlay for human inspection
    * ``debug/{stem}_03_page_detection.json`` — corners, confidence, quads

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: Unused; present for API uniformity.

    Returns:
        Dict with keys ``confidence``, ``is_full_frame``, ``corners``
        (4×2 list), ``photo_quads`` (list of 4×2 lists, may be empty).
    """
    from src.page_detection.detector import detect_page, draw_page_detection

    image = storage.read_image(f"debug/{stem}_02_normalized.jpg")

    detection = detect_page(
        image,
        min_area_ratio=config.page_detect_min_area_ratio,
        grabcut_iterations=config.page_detect_grabcut_iterations,
        grabcut_max_dimension=config.page_detect_grabcut_max_dimension,
    )

    # Debug overlay
    overlay = draw_page_detection(image, detection)
    storage.write_image(f"debug/{stem}_02_page_detected.jpg", overlay, format="jpeg", quality=90)

    # Serialise detection result
    photo_quads = (
        [q.tolist() for q in detection.photo_quads]
        if detection.photo_quads
        else []
    )
    result = {
        "confidence": float(detection.confidence),
        "is_full_frame": bool(detection.is_full_frame),
        "corners": detection.corners.tolist(),
        "photo_quads": photo_quads,
    }
    storage.write_json(f"debug/{stem}_03_page_detection.json", result)

    logger.info(
        "page_detect: confidence=%.2f, is_full_frame=%s, photo_quads=%d",
        detection.confidence,
        detection.is_full_frame,
        len(photo_quads),
    )
    return result
