"""Step: color_restore — white balance, deyellowing, fade restore, sharpening."""

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
    """Apply the full color-restoration chain and write the final output image.

    Sub-steps (all run in sequence):

    1. **White balance** — gray-world; skipped when colour-cast score < 0.08
       to avoid destroying intentional scene colours.
    2. **Deyellowing** — adaptive LAB b* shift.
    3. **Fade restoration** — CLAHE on L channel + saturation boost.
    4. **Sharpening** — adaptive unsharp mask.

    Reads ``debug/{stem}_10_photo_NN_geometry_final.jpg``.
    Writes (all optional debug + final):
    * ``debug/{stem}_11_photo_NN_wb.jpg``
    * ``debug/{stem}_12_photo_NN_deyellow.jpg``
    * ``debug/{stem}_13_photo_NN_restored.jpg``
    * ``debug/{stem}_14_photo_NN_enhanced.jpg``
    * ``output/SundayAlbum_{stem}_PhotoNN.jpg`` — final output

    Args:
        storage: Active storage backend.
        stem: Input file stem.
        config: Pipeline configuration.
        photo_index: 1-based photo index (required).

    Returns:
        Dict with sub-step details (``white_balance``, ``deyellow``,
        ``color_restore``, ``sharpen``).
    """
    if photo_index is None:
        raise ValueError("color_restore.run() requires photo_index")

    from src.color import (
        auto_white_balance,
        assess_white_balance_quality,
        remove_yellowing_adaptive,
        restore_fading,
        enhance,
    )

    idx = f"{photo_index:02d}"
    photo = storage.read_image(f"debug/{stem}_10_photo_{idx}_geometry_final.jpg")
    result: dict = {}

    # 1. White balance
    wb_quality = assess_white_balance_quality(photo)
    if wb_quality["color_cast_score"] > 0.08:
        photo, wb_info = auto_white_balance(photo, page_border=None, method="gray_world")
        result["white_balance"] = {
            "applied": True,
            "cast_score": float(wb_quality["color_cast_score"]),
            "method": wb_info.get("method_used", "gray_world"),
        }
        logger.info(
            "color_restore[%d]: WB applied (cast=%.3f)",
            photo_index,
            wb_quality["color_cast_score"],
        )
    else:
        result["white_balance"] = {
            "applied": False,
            "cast_score": float(wb_quality["color_cast_score"]),
        }
        logger.info(
            "color_restore[%d]: WB skipped (cast=%.3f < 0.08)",
            photo_index,
            wb_quality["color_cast_score"],
        )
    storage.write_image(f"debug/{stem}_11_photo_{idx}_wb.jpg", photo, format="jpeg", quality=95)

    # 2. Deyellowing
    photo, deyellow_info = remove_yellowing_adaptive(photo)
    result["deyellow"] = {
        "corrected": bool(deyellow_info["corrected"]),
        "yellowing_score": float(deyellow_info.get("yellowing_score", 0.0)),
    }
    if deyellow_info["corrected"]:
        logger.debug(
            "color_restore[%d]: deyellow score=%.2f",
            photo_index,
            deyellow_info.get("yellowing_score", 0.0),
        )
        storage.write_image(
            f"debug/{stem}_12_photo_{idx}_deyellow.jpg", photo, format="jpeg", quality=95
        )

    # 3. Fade restoration — adaptive brightness lift + vibrance
    photo, restore_info = restore_fading(
        photo,
        wp_percentile=config.color_restore_wp_percentile,
        wp_target=config.color_restore_wp_target,
        shadow_lift_max=config.color_restore_shadow_lift_max,
        brightness_ceiling=config.color_restore_brightness_ceiling,
        vibrance_boost=config.color_restore_vibrance_boost,
    )
    result["color_restore"] = {
        "wp_scale": float(restore_info.get("wp_scale", 1.0)),
        "shadow_lift_intensity": float(restore_info.get("shadow_lift_intensity", 0.0)),
        "saturation_before": float(restore_info.get("saturation_before", 0.0)),
        "saturation_after": float(restore_info.get("saturation_after", 0.0)),
        "mean_lum_final": float(restore_info.get("mean_lum_final", 0.0)),
    }
    storage.write_image(
        f"debug/{stem}_13_photo_{idx}_restored.jpg", photo, format="jpeg", quality=95
    )

    # 4. Sharpening only — no sigmoid contrast (contrast is handled by color restore)
    photo, enhance_info = enhance(
        photo,
        sharpen_radius=config.sharpen_radius,
        sharpen_amount=config.sharpen_amount,
        apply_contrast=False,
    )
    result["sharpen"] = {
        "sharpen_amount": float(enhance_info.get("sharpen_amount", 0.0)),
        "sharpness_improvement": float(enhance_info.get("sharpness_improvement", 1.0)),
    }
    storage.write_image(
        f"debug/{stem}_14_photo_{idx}_enhanced.jpg", photo, format="jpeg", quality=95
    )

    # Final output
    output_key = f"output/SundayAlbum_{stem}_Photo{idx}.jpg"
    storage.write_image(output_key, photo, format="jpeg", quality=config.jpeg_quality)
    logger.info("color_restore[%d]: wrote %s", photo_index, output_key)

    result["output_key"] = output_key
    return result
