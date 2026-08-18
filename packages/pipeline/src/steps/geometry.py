"""Step: geometry — per-photo geometry correction (rotation, keystone, dewarp)."""

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
    """Apply geometry corrections to a deglared photo.

    Currently active corrections:
    * **Rotation** — small-angle Hough detection returns 0° unconditionally
      (disabled; border-based replacement pending).
    * **Dewarp** — disabled by default (false positives on content).

    The step always writes its output so downstream steps have a predictable
    input key, even if no correction was applied.

    Reads ``debug/{stem}_07_photo_NN_deglared.jpg``.
    Writes ``debug/{stem}_10_photo_NN_geometry_final.jpg``.

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: 1-based photo index (required).

    Returns:
        Dict with ``corrections`` (list of strings), ``rotation_applied`` (float).
    """
    if photo_index is None:
        raise ValueError("geometry.run() requires photo_index")

    idx = f"{photo_index:02d}"
    in_key = f"debug/{stem}_07_photo_{idx}_deglared.jpg"
    out_key = f"debug/{stem}_10_photo_{idx}_geometry_final.jpg"

    from src.geometry import correct_rotation, correct_warp

    photo = storage.read_image(in_key)
    corrected = photo
    corrections: list = []
    rotation_applied: float = 0.0

    # Rotation correction (currently a no-op — returns 0°)
    corrected, angle = correct_rotation(
        corrected, auto_correct_max=config.rotation_auto_correct_max
    )
    if angle != 0.0:
        corrections.append(f"rotation:{angle:.2f}deg")
        rotation_applied = float(angle)
        logger.debug("geometry[%d]: rotation %.2f°", photo_index, angle)

    # Dewarp (disabled by default)
    if config.use_dewarp:
        corrected, warp_detected = correct_warp(corrected)
        if warp_detected:
            corrections.append("dewarp")
            logger.debug("geometry[%d]: dewarp applied", photo_index)

    storage.write_image(out_key, corrected, format="jpeg", quality=95)
    logger.info(
        "geometry[%d]: corrections=%s", photo_index, corrections or ["none"]
    )
    return {"corrections": corrections, "rotation_applied": rotation_applied}
