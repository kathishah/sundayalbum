"""Glare detection for glossy prints and plastic sleeves.

This module detects two types of glare:
1. SLEEVE GLARE: broad, flat patches from plastic album sleeves
2. PRINT GLARE: contoured, curved highlights from glossy photo paper
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple, Literal

import cv2
import numpy as np
from scipy import ndimage

logger = logging.getLogger(__name__)

GlareType = Literal["sleeve", "print", "none"]


@dataclass
class GlareDetection:
    """Result of glare detection on an image."""

    mask: np.ndarray  # Binary mask (H, W) uint8, 255 = glare
    regions: List[np.ndarray]  # List of contours, each shape (N, 1, 2)
    severity_map: np.ndarray  # Float32 (H, W) [0, 1], 0 = no glare, 1 = total glare
    total_glare_area_ratio: float  # Fraction of image affected by glare [0, 1]
    glare_type: GlareType  # "sleeve", "print", or "none"


def detect_glare(
    image: np.ndarray,
    intensity_threshold: float = 0.85,
    saturation_threshold: float = 0.15,
    min_area: int = 100,
    glare_type: str = "auto",
) -> GlareDetection:
    """Detect glare regions in an image.

    Args:
        image: Input image, float32 RGB [0, 1], shape (H, W, 3)
        intensity_threshold: Minimum V (brightness) value for glare [0, 1]
        saturation_threshold: Maximum S (saturation) value for glare [0, 1]
        min_area: Minimum area in pixels for a glare region
        glare_type: "auto" (detect type), "sleeve", "print", or force a type

    Returns:
        GlareDetection with mask, regions, severity map, and classified glare type
    """
    logger.debug(
        f"Detecting glare: intensity_threshold={intensity_threshold}, "
        f"saturation_threshold={saturation_threshold}, min_area={min_area}"
    )

    h, w = image.shape[:2]

    # Convert to HSV color space
    # Glare = high V (brightness) AND low S (saturation)
    # Specular highlights are bright and desaturated
    hsv = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
    h_channel, s_channel, v_channel = cv2.split(hsv)

    # Normalize to [0, 1]
    s_norm = s_channel.astype(np.float32) / 255.0
    v_norm = v_channel.astype(np.float32) / 255.0

    # Step 1: Initial glare detection via HSV thresholding
    # Glare pixels are BRIGHT (high V) and DESATURATED (low S)
    brightness_mask = v_norm > intensity_threshold
    saturation_mask = s_norm < saturation_threshold
    initial_glare_mask = brightness_mask & saturation_mask

    # Step 2: Local texture analysis to reduce false positives
    # Real glare has LOW local texture (uniform bright wash)
    # Bright photo content (white shirt, sky) has HIGHER local texture
    texture_suppressed_mask = _suppress_textured_regions(
        image, initial_glare_mask, window_size=15, texture_threshold=0.02
    )

    # Step 3: Morphological operations to clean up the mask
    # Close to fill small gaps within glare regions
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed_mask = cv2.morphologyEx(
        texture_suppressed_mask.astype(np.uint8) * 255,
        cv2.MORPH_CLOSE,
        kernel_close,
    )

    # Open to remove salt noise (tiny false positives)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned_mask = cv2.morphologyEx(closed_mask, cv2.MORPH_OPEN, kernel_open)

    # Step 4: Filter by minimum region area
    final_mask, regions = _filter_small_regions(cleaned_mask, min_area)

    # Step 5: Compute severity map
    # severity = how far the pixel deviates from expected non-glare value
    severity_map = _compute_severity_map(image, final_mask, v_norm)

    # Step 6: Classify glare type
    total_area_ratio = np.sum(final_mask > 0) / (h * w)

    if glare_type == "auto":
        detected_type = _classify_glare_type(final_mask, regions, total_area_ratio)
    elif glare_type in ("sleeve", "print", "none"):
        detected_type = glare_type  # type: ignore
    else:
        logger.warning(f"Unknown glare_type '{glare_type}', defaulting to 'auto'")
        detected_type = _classify_glare_type(final_mask, regions, total_area_ratio)

    logger.info(
        f"Glare detection complete: {len(regions)} regions, "
        f"area_ratio={total_area_ratio:.3f}, type={detected_type}"
    )

    return GlareDetection(
        mask=final_mask,
        regions=regions,
        severity_map=severity_map,
        total_glare_area_ratio=total_area_ratio,
        glare_type=detected_type,
    )


def _suppress_textured_regions(
    image: np.ndarray, mask: np.ndarray, window_size: int, texture_threshold: float
) -> np.ndarray:
    """Suppress glare detections in regions with high local texture.

    Genuine glare has low local variance (uniform bright wash).
    Bright photo content (sky, white surfaces) has higher local variance.

    Args:
        image: Input image, float32 RGB [0, 1]
        mask: Initial binary mask
        window_size: Size of local window for texture analysis
        texture_threshold: Maximum local std dev for glare [0, 1]

    Returns:
        Binary mask with textured regions suppressed
    """
    # Convert to grayscale for texture analysis
    gray = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    gray_float = gray.astype(np.float32) / 255.0

    # Compute local standard deviation using a sliding window
    # Use scipy's uniform_filter for mean, then compute variance
    local_mean = ndimage.uniform_filter(gray_float, size=window_size)
    local_mean_sq = ndimage.uniform_filter(gray_float**2, size=window_size)
    local_variance = local_mean_sq - local_mean**2
    local_std = np.sqrt(np.maximum(local_variance, 0))

    # Suppress mask pixels where local texture is high
    # High texture = likely photo content, not glare
    low_texture_mask = local_std < texture_threshold
    suppressed_mask = mask & low_texture_mask

    suppressed_count = np.sum(mask) - np.sum(suppressed_mask)
    if suppressed_count > 0:
        logger.debug(
            f"Texture suppression removed {suppressed_count} pixels "
            f"({suppressed_count / np.sum(mask) * 100:.1f}% of initial detections)"
        )

    return suppressed_mask


def _filter_small_regions(mask: np.ndarray, min_area: int) -> Tuple[np.ndarray, List[np.ndarray]]:
    """Filter out glare regions smaller than min_area.

    Args:
        mask: Binary mask uint8, 255 = glare
        min_area: Minimum area in pixels

    Returns:
        Filtered mask and list of region contours
    """
    # Find connected components
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by area
    filtered_contours = []
    filtered_mask = np.zeros_like(mask)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_area:
            filtered_contours.append(contour)
            cv2.drawContours(filtered_mask, [contour], -1, 255, thickness=cv2.FILLED)

    logger.debug(
        f"Region filtering: {len(contours)} initial regions, "
        f"{len(filtered_contours)} after filtering (min_area={min_area})"
    )

    return filtered_mask, filtered_contours


def _compute_severity_map(
    image: np.ndarray, mask: np.ndarray, v_channel: np.ndarray
) -> np.ndarray:
    """Compute per-pixel glare severity.

    Severity indicates how much the pixel is affected by glare:
    - 0.0: no glare or barely affected
    - 1.0: completely washed out, no recoverable detail

    Args:
        image: Input image, float32 RGB [0, 1]
        mask: Binary glare mask uint8, 255 = glare
        v_channel: HSV V channel, float32 [0, 1]

    Returns:
        Severity map, float32 [0, 1]
    """
    h, w = image.shape[:2]
    severity_map = np.zeros((h, w), dtype=np.float32)

    # For glare pixels, severity is based on:
    # 1. How bright the pixel is (higher V = higher severity)
    # 2. Distance from the expected value in surrounding non-glare area

    # Simple approach: map V value in glare regions to severity
    # v = 0.85 -> severity ~0.2 (mild glare)
    # v = 0.95 -> severity ~0.6 (moderate glare)
    # v = 1.0  -> severity ~1.0 (complete washout)

    glare_pixels = mask > 0

    if np.any(glare_pixels):
        # Map brightness to severity with a nonlinear curve
        # Threshold at 0.85, map [0.85, 1.0] -> [0, 1]
        v_glare = v_channel[glare_pixels]
        severity_raw = (v_glare - 0.85) / 0.15  # Linear map [0.85, 1.0] -> [0, 1]
        severity_raw = np.clip(severity_raw, 0, 1)

        # Apply power curve to emphasize severe glare
        severity_curved = severity_raw**0.7  # Slight compression

        severity_map[glare_pixels] = severity_curved

        logger.debug(
            f"Severity map: mean={np.mean(severity_curved):.3f}, "
            f"max={np.max(severity_curved):.3f}"
        )

    return severity_map


def _classify_glare_type(
    mask: np.ndarray, regions: List[np.ndarray], total_area_ratio: float
) -> GlareType:
    """Classify the type of glare detected.

    SLEEVE GLARE:
    - Fewer, larger, more uniform regions
    - Often near center of page
    - Broader, flatter distribution

    PRINT GLARE:
    - More irregular shapes
    - Follows contours (may be elongated or curved)
    - Can be scattered across the image

    Args:
        mask: Binary glare mask
        regions: List of detected contours
        total_area_ratio: Fraction of image covered by glare

    Returns:
        "sleeve", "print", or "none"
    """
    if total_area_ratio < 0.01 or len(regions) == 0:
        return "none"

    # Compute features for classification
    num_regions = len(regions)
    region_areas = [cv2.contourArea(r) for r in regions]
    mean_area = np.mean(region_areas)
    max_area = np.max(region_areas)

    # Compute shape irregularity for each region
    # Irregularity = perimeter^2 / (4 * pi * area)
    # Circle = 1.0, more irregular shapes > 1.0
    irregularities = []
    for region in regions:
        area = cv2.contourArea(region)
        perimeter = cv2.arcLength(region, closed=True)
        if area > 0:
            irregularity = (perimeter**2) / (4 * np.pi * area + 1e-6)
            irregularities.append(irregularity)

    mean_irregularity = np.mean(irregularities) if irregularities else 1.0

    # Classification heuristics:
    # SLEEVE: Few large uniform blobs (1-3 regions, low irregularity)
    # PRINT: More scattered, irregular (multiple regions, higher irregularity)

    logger.debug(
        f"Glare classification features: num_regions={num_regions}, "
        f"mean_area={mean_area:.1f}, mean_irregularity={mean_irregularity:.2f}"
    )

    # Decision tree
    if num_regions <= 3 and mean_irregularity < 2.5 and max_area > 5000:
        # Few large uniform blobs -> likely sleeve glare
        return "sleeve"
    elif mean_irregularity > 3.0 or num_regions > 5:
        # Many irregular regions -> likely print glare
        return "print"
    else:
        # Ambiguous, default to print (more conservative for removal)
        return "print"


def draw_glare_overlay(
    image: np.ndarray, detection: GlareDetection, overlay_color: Tuple[int, int, int] = (255, 100, 0)
) -> np.ndarray:
    """Draw glare detection overlay on the original image.

    Args:
        image: Original image, float32 RGB [0, 1]
        detection: GlareDetection result
        overlay_color: RGB color for overlay (default: orange)

    Returns:
        Image with semi-transparent overlay on glare regions, uint8 RGB
    """
    # Convert to uint8
    img_uint8 = (image * 255).astype(np.uint8)

    # Create colored overlay weighted by severity
    overlay = img_uint8.copy()

    # Create color mask
    color_mask = np.zeros_like(img_uint8)
    color_mask[:, :] = overlay_color

    # Blend based on severity (higher severity = more opaque overlay)
    severity_3ch = np.stack([detection.severity_map] * 3, axis=-1)
    alpha = severity_3ch * 0.6  # Max 60% opacity

    glare_pixels = detection.mask > 0
    overlay[glare_pixels] = (
        img_uint8[glare_pixels] * (1 - alpha[glare_pixels])
        + color_mask[glare_pixels] * alpha[glare_pixels]
    ).astype(np.uint8)

    # Draw contours in bright red
    cv2.drawContours(overlay, detection.regions, -1, (255, 0, 0), 2)

    return overlay
