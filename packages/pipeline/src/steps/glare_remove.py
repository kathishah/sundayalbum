"""Step: glare_remove — OpenAI or OpenCV glare removal per photo."""

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
    """Remove glare from an oriented photo.

    Default path: OpenAI ``gpt-image-1.5`` images.edit (semantic inpainting).
    Fallback: OpenCV inpainting (used when OPENAI_API_KEY is absent or
    ``config.use_openai_glare_removal`` is False).

    Reads:
    * ``debug/{stem}_05b_photo_NN_oriented.jpg``
    * ``debug/{stem}_05b_photo_NN_analysis.json`` (for ``scene_description``)

    Writes ``debug/{stem}_07_photo_NN_deglared.jpg``.

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: 1-based photo index (required).

    Returns:
        Dict with ``method`` (``"openai"``, ``"opencv"``, or ``"passthrough"``).
    """
    if photo_index is None:
        raise ValueError("glare_remove.run() requires photo_index")

    idx = f"{photo_index:02d}"
    in_key = f"debug/{stem}_05b_photo_{idx}_oriented.jpg"
    out_key = f"debug/{stem}_07_photo_{idx}_deglared.jpg"

    image = storage.read_image(in_key)

    # Load scene description from orientation analysis (best-effort)
    scene_desc = "A printed photograph."
    analysis_key = f"debug/{stem}_05b_photo_{idx}_analysis.json"
    if storage.exists(analysis_key):
        try:
            analysis = storage.read_json(analysis_key)
            scene_desc = (
                config.forced_scene_description
                or analysis.get("scene_description", "")
                or "A printed photograph."
            )
        except Exception:
            pass

    use_openai = config.use_openai_glare_removal
    openai_key = config.openai_api_key or None

    if use_openai and not openai_key:
        logger.warning(
            "glare_remove[%d]: openai_api_key not set in config — falling back to OpenCV",
            photo_index,
        )
        use_openai = False

    if use_openai and openai_key:
        from src.glare.remover_openai import remove_glare_openai
        deglared = remove_glare_openai(
            image,
            scene_desc=scene_desc,
            api_key=openai_key,
            model=config.openai_model,
            quality=config.openai_glare_quality,
            input_fidelity=config.openai_glare_input_fidelity,
        )
        storage.write_image(out_key, deglared, format="jpeg", quality=95)
        logger.info("glare_remove[%d]: OpenAI path complete", photo_index)
        return {"method": "openai"}

    # OpenCV fallback
    from src.glare.detector import detect_glare, draw_glare_overlay
    from src.glare.remover_single import remove_glare_single

    glare = detect_glare(
        image,
        intensity_threshold=config.glare_intensity_threshold,
        saturation_threshold=config.glare_saturation_threshold,
        min_area=config.glare_min_area,
        glare_type=config.glare_type,
    )

    if glare.total_glare_area_ratio > 0.001:
        result = remove_glare_single(
            image,
            glare.mask,
            glare.severity_map,
            inpaint_radius=config.glare_inpaint_radius,
            feather_radius=config.glare_feather_radius,
        )
        deglared = result.image
        method = "opencv"

        # Save glare mask for first photo (debug only)
        if photo_index == 1:
            storage.write_image(
                f"debug/{stem}_06_photo_{idx}_glare_mask.png",
                glare.mask,
                format="png",
            )
            overlay = draw_glare_overlay(image, glare)
            storage.write_image(
                f"debug/{stem}_06_photo_{idx}_glare_overlay.jpg",
                overlay,
                format="jpeg",
                quality=90,
            )
    else:
        deglared = image
        method = "passthrough"
        logger.debug("glare_remove[%d]: no significant glare — pass-through", photo_index)

    storage.write_image(out_key, deglared, format="jpeg", quality=95)
    logger.info("glare_remove[%d]: %s path complete", photo_index, method)
    return {"method": method}
