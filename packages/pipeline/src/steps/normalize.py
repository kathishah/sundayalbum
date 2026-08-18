"""Step: normalize — resize to working resolution, write debug frame."""

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
    """Resize and normalise the loaded image for pipeline processing.

    Reads ``debug/{stem}_01_loaded.jpg``.
    Writes ``debug/{stem}_02_normalized.jpg``.

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration (uses ``max_working_resolution``).
        photo_index: Unused; present for API uniformity.

    Returns:
        Dict with keys ``width``, ``height``, ``scale_factor``.
    """
    from src.preprocessing.normalizer import normalize

    image = storage.read_image(f"debug/{stem}_01_loaded.jpg")
    logger.info("normalize: input shape %s", image.shape)

    result = normalize(image, config.max_working_resolution)
    working = result.image

    storage.write_image(f"debug/{stem}_02_normalized.jpg", working, format="jpeg", quality=95)

    h, w = working.shape[:2]
    orig_h, orig_w = image.shape[:2]
    scale = w / orig_w if orig_w > 0 else 1.0
    logger.info("normalize: %dx%d → %dx%d (scale=%.3f)", orig_w, orig_h, w, h, scale)

    return {"width": w, "height": h, "scale_factor": scale}
