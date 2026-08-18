"""Single-shot glare removal using inpainting and intensity correction.

This module removes glare from a single image using three approaches:
1. INTENSITY CORRECTION: For mild glare (severity < 0.4) - preserves underlying detail
2. OPENCV INPAINTING: For moderate glare (0.4-0.7) - fills from surrounding context
3. CONTEXTUAL FILL: For severe glare (> 0.7) - multi-scale reconstruction
"""

import logging
from dataclasses import dataclass
from typing import Tuple, Literal

import cv2
import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

logger = logging.getLogger(__name__)

RemovalMethod = Literal["intensity", "inpaint_telea", "inpaint_ns", "contextual"]


@dataclass
class GlareResult:
    """Result of glare removal operation."""

    image: np.ndarray  # Corrected image, float32 RGB [0, 1], shape (H, W, 3)
    confidence_map: np.ndarray  # Per-pixel confidence [0, 1], shape (H, W)
    method_used: dict  # Dict mapping method name to % of pixels processed by that method


def remove_glare_single(
    image: np.ndarray,
    glare_mask: np.ndarray,
    severity_map: np.ndarray,
    inpaint_radius: int = 5,
    feather_radius: int = 5,
) -> GlareResult:
    """Remove glare from a single image using hybrid approach.

    Args:
        image: Input image, float32 RGB [0, 1], shape (H, W, 3)
        glare_mask: Binary mask, uint8 (H, W), 255 = glare
        severity_map: Severity per pixel, float32 [0, 1], shape (H, W)
        inpaint_radius: Radius for inpainting algorithms (pixels)
        feather_radius: Radius for mask feathering (pixels)

    Returns:
        GlareResult with corrected image, confidence map, and method breakdown
    """
    logger.debug(
        f"Removing glare: inpaint_radius={inpaint_radius}, feather_radius={feather_radius}"
    )

    h, w = image.shape[:2]

    # If no glare, return original with perfect confidence
    if glare_mask.max() == 0:
        logger.debug("No glare detected, returning original image")
        return GlareResult(
            image=image.copy(),
            confidence_map=np.ones((h, w), dtype=np.float32),
            method_used={"none": 100.0},
        )

    # Create binary mask (0 or 1) from the uint8 mask
    mask_binary = (glare_mask > 0).astype(np.float32)

    # Feather the mask boundary to avoid hard transitions
    feathered_mask = _feather_mask(mask_binary, feather_radius)

    # Classify each glare pixel by severity
    # mild: severity < 0.4
    # moderate: 0.4 <= severity < 0.7
    # severe: severity >= 0.7
    mild_mask = (mask_binary > 0) & (severity_map < 0.4)
    moderate_mask = (mask_binary > 0) & (severity_map >= 0.4) & (severity_map < 0.7)
    severe_mask = (mask_binary > 0) & (severity_map >= 0.7)

    # Initialize result image and confidence map
    result = image.copy()
    confidence = np.ones((h, w), dtype=np.float32)

    # Track method usage
    total_glare_pixels = mask_binary.sum()
    method_pixels = {
        "intensity": mild_mask.sum(),
        "inpaint": moderate_mask.sum(),
        "contextual": severe_mask.sum(),
    }

    # Step 1: INTENSITY CORRECTION for mild glare
    if mild_mask.any():
        logger.debug(
            f"Applying intensity correction to {mild_mask.sum():.0f} mild glare pixels"
        )
        result, mild_confidence = _apply_intensity_correction(
            result, mild_mask, severity_map, image
        )
        confidence = np.where(mild_mask, mild_confidence, confidence)

    # Step 2: OPENCV INPAINTING for moderate glare
    if moderate_mask.any():
        logger.debug(
            f"Applying inpainting to {moderate_mask.sum():.0f} moderate glare pixels"
        )
        result, inpaint_confidence = _apply_inpainting(
            result, moderate_mask, inpaint_radius
        )
        confidence = np.where(moderate_mask, inpaint_confidence, confidence)

    # Step 3: CONTEXTUAL FILL for severe glare
    if severe_mask.any():
        logger.debug(
            f"Applying contextual fill to {severe_mask.sum():.0f} severe glare pixels"
        )
        result, contextual_confidence = _apply_contextual_fill(
            result, severe_mask, image
        )
        confidence = np.where(severe_mask, contextual_confidence, confidence)

    # Step 4: POST-PROCESSING
    # Blend result with original using feathered mask for smooth transitions
    result = _blend_with_feathering(image, result, feathered_mask)

    # Color/brightness matching at boundaries
    result = _match_boundary_colors(result, mask_binary, image)

    # Compute method usage percentages
    if total_glare_pixels > 0:
        method_used = {
            method: (count / total_glare_pixels * 100.0)
            for method, count in method_pixels.items()
        }
    else:
        method_used = {"none": 100.0}

    logger.debug(f"Glare removal complete. Method breakdown: {method_used}")

    return GlareResult(
        image=result, confidence_map=confidence, method_used=method_used
    )


def _feather_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Apply Gaussian blur to mask for smooth transitions.

    Args:
        mask: Binary mask, float32 [0, 1], shape (H, W)
        radius: Blur radius in pixels

    Returns:
        Feathered mask, float32 [0, 1], shape (H, W)
    """
    if radius <= 0:
        return mask

    sigma = radius / 2.0
    feathered = gaussian_filter(mask, sigma=sigma, mode="nearest")
    return np.clip(feathered, 0.0, 1.0)


def _apply_intensity_correction(
    image: np.ndarray,
    mask: np.ndarray,
    severity_map: np.ndarray,
    original: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply intensity correction for mild glare.

    For mild glare, the underlying image is partially visible (just washed out).
    We estimate what the pixel should look like by sampling non-glare neighbors
    and adjusting intensity based on severity.

    Args:
        image: Current image, float32 RGB [0, 1], shape (H, W, 3)
        mask: Binary mask for mild glare regions, bool, shape (H, W)
        severity_map: Severity per pixel, float32 [0, 1], shape (H, W)
        original: Original image (for reference), float32 RGB [0, 1], shape (H, W, 3)

    Returns:
        Tuple of (corrected_image, confidence_map)
    """
    result = image.copy()
    h, w = image.shape[:2]
    confidence = np.ones((h, w), dtype=np.float32)

    # For each channel, estimate the expected value from surrounding non-glare pixels
    for c in range(3):
        channel = image[:, :, c]

        # Dilate the mask to get a neighborhood for sampling
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        neighborhood = cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)

        # Non-glare pixels in the neighborhood
        sample_mask = neighborhood & ~mask

        if sample_mask.any():
            # Get statistics from non-glare neighbors
            neighbor_mean = channel[sample_mask].mean()
            neighbor_std = channel[sample_mask].std()

            # For glare pixels, blend between original and estimated value
            # Higher severity = more adjustment needed
            severity_in_mask = severity_map[mask]
            original_values = original[mask, c]

            # Estimate what pixel should be (simple darkening based on neighbors)
            # This is a simplified model - could be more sophisticated
            estimated_values = np.clip(
                original_values * (1.0 - severity_in_mask * 0.5), 0.0, 1.0
            )

            # Confidence is higher for lower severity (we can see through mild glare)
            confidence[mask] = 1.0 - severity_in_mask * 0.5

            # Update channel
            result[mask, c] = estimated_values
        else:
            # No non-glare neighbors found, reduce confidence
            confidence[mask] = 0.5

    return result, confidence


def _apply_inpainting(
    image: np.ndarray, mask: np.ndarray, radius: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply OpenCV inpainting for moderate glare.

    Tries both TELEA and NS inpainting algorithms and picks the better result
    based on boundary error.

    Args:
        image: Input image, float32 RGB [0, 1], shape (H, W, 3)
        mask: Binary mask for moderate glare, bool, shape (H, W)
        radius: Inpainting radius in pixels

    Returns:
        Tuple of (inpainted_image, confidence_map)
    """
    h, w = image.shape[:2]

    # Convert to uint8 for OpenCV inpainting
    image_uint8 = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
    mask_uint8 = mask.astype(np.uint8) * 255

    # Try both inpainting methods
    try:
        inpaint_telea = cv2.inpaint(image_uint8, mask_uint8, radius, cv2.INPAINT_TELEA)
        inpaint_ns = cv2.inpaint(image_uint8, mask_uint8, radius, cv2.INPAINT_NS)

        # Compare boundary quality - which one has smoother transition?
        # Erode mask to get boundary region
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_eroded = cv2.erode(mask_uint8, kernel)
        boundary = (mask_uint8 > 0) & (mask_eroded == 0)

        if boundary.any():
            # Compute boundary smoothness (lower variance = better)
            boundary_variance_telea = np.var(inpaint_telea[boundary])
            boundary_variance_ns = np.var(inpaint_ns[boundary])

            if boundary_variance_telea < boundary_variance_ns:
                result_uint8 = inpaint_telea
                method = "telea"
            else:
                result_uint8 = inpaint_ns
                method = "ns"
        else:
            # Default to TELEA if no boundary found
            result_uint8 = inpaint_telea
            method = "telea"

        logger.debug(f"Selected inpainting method: {method}")

    except Exception as e:
        logger.warning(f"Inpainting failed: {e}, using TELEA only")
        result_uint8 = cv2.inpaint(image_uint8, mask_uint8, radius, cv2.INPAINT_TELEA)

    # Convert back to float32
    result = result_uint8.astype(np.float32) / 255.0

    # Confidence for inpainting is moderate (we're guessing based on neighbors)
    confidence = np.ones((h, w), dtype=np.float32)
    confidence[mask] = 0.6  # Moderate confidence for inpainted regions

    return result, confidence


def _apply_contextual_fill(
    image: np.ndarray, mask: np.ndarray, original: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply contextual fill for severe glare using multi-scale approach.

    For large severely washed-out areas, simple inpainting produces smears.
    Use multi-scale approach: inpaint at low res, refine at high res.

    Args:
        image: Input image, float32 RGB [0, 1], shape (H, W, 3)
        mask: Binary mask for severe glare, bool, shape (H, W)
        original: Original image (for reference), float32 RGB [0, 1], shape (H, W, 3)

    Returns:
        Tuple of (filled_image, confidence_map)
    """
    h, w = image.shape[:2]
    result = image.copy()

    # Multi-scale inpainting
    # Step 1: Downsample to 1/4 resolution
    scale = 0.25
    small_h, small_w = int(h * scale), int(w * scale)

    image_small = cv2.resize(
        (image * 255).astype(np.uint8), (small_w, small_h), interpolation=cv2.INTER_AREA
    )
    mask_small = cv2.resize(
        mask.astype(np.uint8) * 255, (small_w, small_h), interpolation=cv2.INTER_NEAREST
    )

    # Inpaint at low resolution with larger radius
    inpaint_radius = max(3, int(min(small_h, small_w) * 0.05))
    try:
        inpaint_small = cv2.inpaint(
            image_small, mask_small, inpaint_radius, cv2.INPAINT_TELEA
        )
    except Exception as e:
        logger.warning(f"Low-res inpainting failed: {e}")
        inpaint_small = image_small

    # Upsample back to original resolution
    inpaint_upsampled = cv2.resize(
        inpaint_small, (w, h), interpolation=cv2.INTER_CUBIC
    )
    inpaint_upsampled = inpaint_upsampled.astype(np.float32) / 255.0

    # Step 2: Refine at full resolution in glare regions only
    result_uint8 = (np.clip(result, 0.0, 1.0) * 255).astype(np.uint8)
    mask_uint8 = mask.astype(np.uint8) * 255

    # Smaller radius for refinement
    refine_radius = 3
    try:
        refined = cv2.inpaint(result_uint8, mask_uint8, refine_radius, cv2.INPAINT_NS)
        refined_float = refined.astype(np.float32) / 255.0
    except Exception as e:
        logger.warning(f"High-res refinement failed: {e}")
        refined_float = result

    # Blend low-res and high-res results
    # Use low-res for structure, high-res for detail
    blend_weight = 0.6  # 60% low-res (structure), 40% high-res (detail)
    result[mask] = (
        blend_weight * inpaint_upsampled[mask] + (1.0 - blend_weight) * refined_float[mask]
    )

    # Confidence is low for severe glare (we're making educated guesses)
    confidence = np.ones((h, w), dtype=np.float32)
    confidence[mask] = 0.3  # Low confidence for severe glare reconstruction

    return result, confidence


def _blend_with_feathering(
    original: np.ndarray, corrected: np.ndarray, feathered_mask: np.ndarray
) -> np.ndarray:
    """Blend original and corrected images using feathered mask.

    Args:
        original: Original image, float32 RGB [0, 1], shape (H, W, 3)
        corrected: Corrected image, float32 RGB [0, 1], shape (H, W, 3)
        feathered_mask: Feathered mask [0, 1], shape (H, W)

    Returns:
        Blended image, float32 RGB [0, 1], shape (H, W, 3)
    """
    # Expand mask to 3 channels
    mask_3ch = feathered_mask[:, :, np.newaxis]

    # Blend: result = original * (1 - mask) + corrected * mask
    blended = original * (1.0 - mask_3ch) + corrected * mask_3ch

    return np.clip(blended, 0.0, 1.0)


def _match_boundary_colors(
    image: np.ndarray, mask: np.ndarray, reference: np.ndarray
) -> np.ndarray:
    """Match color/brightness at glare boundaries to surrounding area.

    This reduces visible seams at the boundary between corrected and original regions.

    Args:
        image: Corrected image, float32 RGB [0, 1], shape (H, W, 3)
        mask: Binary glare mask, float32 [0, 1], shape (H, W)
        reference: Original/reference image, float32 RGB [0, 1], shape (H, W, 3)

    Returns:
        Color-matched image, float32 RGB [0, 1], shape (H, W, 3)
    """
    result = image.copy()

    # Get boundary region (pixels just inside the mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask_uint8 = (mask > 0.5).astype(np.uint8) * 255
    mask_eroded = cv2.erode(mask_uint8, kernel)
    boundary_inside = (mask_uint8 > 0) & (mask_eroded == 0)

    # Get border region (pixels just outside the mask)
    mask_dilated = cv2.dilate(mask_uint8, kernel)
    boundary_outside = (mask_dilated > 0) & (mask_uint8 == 0)

    if boundary_inside.any() and boundary_outside.any():
        # For each channel, match mean and std at boundary
        for c in range(3):
            # Reference statistics from outside boundary
            ref_mean = reference[boundary_outside, c].mean()
            ref_std = reference[boundary_outside, c].std()

            # Current statistics at inside boundary
            curr_mean = result[boundary_inside, c].mean()
            curr_std = result[boundary_inside, c].std()

            if curr_std > 1e-6:  # Avoid division by zero
                # Apply linear transformation to match statistics
                # Scale to match std, then shift to match mean
                alpha = ref_std / (curr_std + 1e-6)
                beta = ref_mean - alpha * curr_mean

                # Apply transformation only to glare regions
                glare_pixels = mask > 0.5
                result[glare_pixels, c] = np.clip(
                    alpha * result[glare_pixels, c] + beta, 0.0, 1.0
                )

    return result
