"""Fade restoration for aged photos using adaptive brightness lift and vibrance.

Replaces the previous CLAHE-based approach which caused two regressions:
  - Dimming: CLAHE redistributed luminance across local tiles, pulling highlights
    down on already well-exposed photos.
  - Grain: CLAHE amplified sensor noise in smooth-toned regions (sky, walls).

The new algorithm has three self-limiting stages:
  1. White-point stretch  — scale so the 99th-percentile luminance hits 0.96.
     Already-bright photos barely change; faded ones lift naturally.
  2. Shadow lift          — tone-curve lift applied only to dark pixels, leaving
     highlights untouched.  Skipped entirely when the image is already bright.
     Preserves intentionally dark scenes (cave, candlelit dinner).
  3. Vibrance saturation  — per-pixel saturation boost inversely proportional to
     existing saturation.  Already-vivid colours are protected; faded/muted ones
     lift the most.

A brightness ceiling guard at the end scales back if the mean luminance overshoots.
"""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def restore_fading(
    photo: np.ndarray,
    wp_percentile: float = 99.0,
    wp_target: float = 0.96,
    shadow_lift_max: float = 0.15,
    brightness_ceiling: float = 0.75,
    vibrance_boost: float = 0.25,
) -> Tuple[np.ndarray, dict]:
    """Restore exposure and colour vibrancy to a faded photo.

    Args:
        photo: Input image as float32 RGB [0, 1], shape (H, W, 3).
        wp_percentile: Percentile of luminance used as the white-point
            reference (default 99 — ignores the top 1 % as potential glare).
        wp_target: Target value that ``wp_percentile`` is scaled to.
            0.96 leaves 4 % headroom to avoid clipping.
        shadow_lift_max: Maximum additive lift applied to the darkest pixels
            in Stage 2.  0.15 ≈ lifting pure black to 15 % grey.
        brightness_ceiling: If mean luminance after all stages exceeds this
            value the image is scaled back proportionally.  Prevents
            over-brightening images that are already well-exposed.
        vibrance_boost: Base per-pixel saturation boost for Stage 3.
            The effective boost is ``vibrance_boost * (1 − current_sat)``,
            so already-vivid pixels receive near-zero additional saturation.

    Returns:
        Tuple of:
            - Restored image as float32 RGB [0, 1].
            - Info dict with metrics about each stage.
    """
    if photo.ndim != 3 or photo.shape[2] != 3:
        logger.warning("restore_fading: invalid shape %s, returning unchanged", photo.shape)
        return photo, {"error": "invalid_shape"}

    result: dict = {}
    img = photo.copy()

    # ------------------------------------------------------------------
    # Stage 1: White-point stretch
    # ------------------------------------------------------------------
    lum = _luminance(img)
    wp_before = float(np.percentile(lum, wp_percentile))
    result["wp_before"] = wp_before

    if wp_before > 0.05:
        scale = wp_target / wp_before
        scale = float(np.clip(scale, 1.0, 2.0))  # never darken; cap lift at 2×
        img = np.clip(img * scale, 0.0, 1.0)
        logger.debug(
            "restore_fading: Stage 1 — wp=%.3f → scale=%.3f", wp_before, scale
        )
    else:
        scale = 1.0
        logger.debug("restore_fading: Stage 1 skipped — image nearly black (wp=%.3f)", wp_before)

    result["wp_scale"] = scale

    # ------------------------------------------------------------------
    # Stage 2: Shadow lift (skipped when image already bright)
    # ------------------------------------------------------------------
    mean_lum_after_stretch = float(np.mean(_luminance(img)))
    result["mean_lum_after_stretch"] = mean_lum_after_stretch

    brightness_threshold = 0.60
    if mean_lum_after_stretch < brightness_threshold:
        # Intensity proportional to how far below the threshold we are
        intensity = np.clip(
            (brightness_threshold - mean_lum_after_stretch) / brightness_threshold,
            0.0,
            1.0,
        )
        # Per-pixel lift: quadratic falloff — dark pixels get max_lift,
        # bright pixels (near 1.0) get ~0.  Applied uniformly per channel
        # so colour ratios are preserved.
        lift = shadow_lift_max * intensity * (1.0 - img) ** 2
        img = np.clip(img + lift, 0.0, 1.0)
        logger.debug(
            "restore_fading: Stage 2 — mean_lum=%.3f, intensity=%.3f, lift_max=%.3f",
            mean_lum_after_stretch,
            intensity,
            shadow_lift_max * intensity,
        )
        result["shadow_lift_intensity"] = float(intensity)
    else:
        logger.debug(
            "restore_fading: Stage 2 skipped — image already bright (mean_lum=%.3f)",
            mean_lum_after_stretch,
        )
        result["shadow_lift_intensity"] = 0.0

    # ------------------------------------------------------------------
    # Stage 3: Vibrance-style saturation boost
    # ------------------------------------------------------------------
    img_uint8 = (img * 255.0).astype(np.uint8)
    hsv = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)

    S = hsv[:, :, 1]  # [0, 255]
    V = hsv[:, :, 2]  # [0, 255]
    mean_sat_before = float(np.mean(S)) / 255.0

    # Boost is weighted by two factors:
    #   1. Saturation weight:  (1 - S/255) — already-vivid colours get less boost
    #   2. Value weight:       (1 - (V/255)^2) — near-white/highlight pixels get
    #      near-zero boost.  This prevents undefined/noisy Hue values in bright
    #      areas (white car, oily skin, sky) from being amplified into a visible
    #      pink or yellow tint.
    sat_weight = 1.0 - S / 255.0
    value_weight = 1.0 - (V / 255.0) ** 2
    boost_per_pixel = vibrance_boost * sat_weight * value_weight
    S_new = np.clip(S + boost_per_pixel * 255.0, 0.0, 255.0)
    hsv[:, :, 1] = S_new

    img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0
    mean_sat_after = float(np.mean(S_new)) / 255.0

    logger.debug(
        "restore_fading: Stage 3 — saturation %.3f → %.3f", mean_sat_before, mean_sat_after
    )
    result["saturation_before"] = mean_sat_before
    result["saturation_after"] = mean_sat_after

    # ------------------------------------------------------------------
    # Brightness ceiling guard
    # ------------------------------------------------------------------
    mean_lum_final = float(np.mean(_luminance(img)))
    if mean_lum_final > brightness_ceiling:
        scale_down = brightness_ceiling / mean_lum_final
        img = np.clip(img * scale_down, 0.0, 1.0)
        logger.debug(
            "restore_fading: ceiling guard — mean_lum=%.3f → scaled down by %.3f",
            mean_lum_final,
            scale_down,
        )
        result["ceiling_scale_down"] = float(scale_down)
        mean_lum_final = float(np.mean(_luminance(img)))
    else:
        result["ceiling_scale_down"] = 1.0

    result["mean_lum_final"] = mean_lum_final

    logger.info(
        "restore_fading: wp_scale=%.2f  shadow_lift=%.2f  sat %.3f→%.3f  mean_lum=%.3f",
        scale,
        result["shadow_lift_intensity"],
        mean_sat_before,
        mean_sat_after,
        mean_lum_final,
    )

    return img, result


def restore_fading_conservative(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Restore fading with conservative settings — subtle enhancement only.

    Args:
        photo: Input image as float32 RGB [0, 1].

    Returns:
        Tuple of (restored image, info dict).
    """
    return restore_fading(
        photo,
        wp_percentile=99.0,
        wp_target=0.92,         # gentler stretch target
        shadow_lift_max=0.08,   # half the default lift
        brightness_ceiling=0.72,
        vibrance_boost=0.15,    # half the default vibrance
    )


def restore_fading_aggressive(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Restore fading with aggressive settings for heavily faded photos.

    Args:
        photo: Input image as float32 RGB [0, 1].

    Returns:
        Tuple of (restored image, info dict).
    """
    return restore_fading(
        photo,
        wp_percentile=98.0,     # use 98th percentile — more aggressive stretch
        wp_target=0.98,
        shadow_lift_max=0.25,
        brightness_ceiling=0.80,
        vibrance_boost=0.40,
    )


def assess_fading(photo: np.ndarray) -> dict:
    """Assess whether a photo is faded and needs restoration.

    Retained for diagnostic use.  The new ``restore_fading`` algorithm is
    self-limiting and does not require this gate, but the metrics are still
    useful for logging and debugging.

    Args:
        photo: Input image as float32 RGB [0, 1].

    Returns:
        Dict with ``is_faded`` (bool), ``fading_score`` (0–1),
        ``contrast_score``, ``mean_saturation``, and
        ``saturation_percentile_25``.
    """
    photo_uint8 = (photo * 255).astype(np.uint8)
    gray = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2GRAY)

    contrast_score = _compute_local_contrast(gray, kernel_size=5)
    normalized_contrast = contrast_score / 25.0

    hsv = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1].astype(np.float32) / 255.0

    mean_saturation = float(np.mean(saturation))
    saturation_p25 = float(np.percentile(saturation, 25))

    contrast_deficit = max(0.0, 0.8 - normalized_contrast)
    saturation_deficit = max(0.0, 0.3 - mean_saturation)

    fading_score = (contrast_deficit + saturation_deficit * 2) / 3.0
    is_faded = fading_score > 0.2

    return {
        "is_faded": bool(is_faded),
        "fading_score": float(fading_score),
        "contrast_score": float(contrast_score),
        "normalized_contrast": float(normalized_contrast),
        "mean_saturation": mean_saturation,
        "saturation_percentile_25": saturation_p25,
    }


# ---------------------------------------------------------------------------
# Legacy (kept for side-by-side comparison if needed, not called by pipeline)
# ---------------------------------------------------------------------------

def _restore_fading_clahe_legacy(
    photo: np.ndarray,
    clahe_clip_limit: float = 2.0,
    clahe_grid_size: tuple = (8, 8),
    saturation_boost: float = 0.15,
    auto_detect_fading: bool = True,
) -> Tuple[np.ndarray, dict]:
    """CLAHE-based fade restoration — legacy implementation, not in active use.

    Retained so the old behaviour can be compared against the new algorithm
    during evaluation.  Do not call from the pipeline.
    """
    photo_uint8 = (photo * 255).astype(np.uint8)
    lab = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2LAB)
    L, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=clahe_grid_size)
    L_clahe = clahe.apply(L)

    lab_clahe = cv2.merge([L_clahe, a, b])
    rgb_clahe = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2RGB).astype(np.float32) / 255.0

    if auto_detect_fading:
        fading_info = assess_fading(photo)
        if fading_info["is_faded"]:
            fading_severity = fading_info["fading_score"]
            adaptive_boost = saturation_boost * min(1.0, fading_severity / 0.3)
            result_img = _boost_saturation_fixed(rgb_clahe, adaptive_boost)
        else:
            result_img = rgb_clahe
    else:
        result_img = _boost_saturation_fixed(rgb_clahe, saturation_boost)

    return result_img, {"legacy_clahe": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _luminance(img: np.ndarray) -> np.ndarray:
    """Return perceptual luminance array (float32, same H×W as img)."""
    return 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]


def _compute_local_contrast(gray_image: np.ndarray, kernel_size: int = 5) -> float:
    """Compute average local contrast via local standard deviation."""
    img_float = gray_image.astype(np.float32)
    kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)
    local_mean = cv2.filter2D(img_float, -1, kernel)
    local_mean_sq = cv2.filter2D(img_float ** 2, -1, kernel)
    local_var = np.maximum(local_mean_sq - local_mean ** 2, 0)
    return float(np.mean(np.sqrt(local_var)))


def _boost_saturation_fixed(photo: np.ndarray, boost: float) -> np.ndarray:
    """Fixed-multiplier saturation boost (used only by the legacy path)."""
    if boost <= 0.0:
        return photo
    photo_uint8 = (photo * 255).astype(np.uint8)
    hsv = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1.0 + boost), 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0
