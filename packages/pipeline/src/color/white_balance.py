"""White balance correction for color restoration.

This module implements automatic white balance correction to fix color casts
from aged photos or incorrect lighting during capture.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def auto_white_balance(
    photo: np.ndarray,
    page_border: Optional[np.ndarray] = None,
    method: str = "gray_world"
) -> Tuple[np.ndarray, dict]:
    """Apply automatic white balance correction to a photo.

    Uses the gray-world assumption: the average color in the image should be gray.
    If page border pixels are provided (from album page detection), they are used
    as a neutral reference since album pages are typically white or off-white.

    Args:
        photo: Input image as float32 RGB [0, 1], shape (H, W, 3)
        page_border: Optional border pixels as float32 RGB [0, 1], shape (N, 3)
        method: White balance method - "gray_world", "white_patch", or "border"

    Returns:
        Tuple of:
            - White-balanced image as float32 RGB [0, 1]
            - Info dict with 'method_used', 'gain_r', 'gain_g', 'gain_b'
    """
    if photo.ndim != 3 or photo.shape[2] != 3:
        logger.warning(f"Invalid photo shape: {photo.shape}, expected (H, W, 3)")
        return photo, {'method_used': 'none', 'error': 'invalid_shape'}

    # If page border available and method allows, use it as neutral reference
    if page_border is not None and len(page_border) > 100 and method == "border":
        logger.debug(f"Using page border ({len(page_border)} pixels) for white balance")
        balanced, info = _white_balance_from_reference(photo, page_border)
        info['method_used'] = 'border_reference'
        return balanced, info

    # Otherwise use gray-world assumption
    if method == "white_patch":
        balanced, info = _white_balance_white_patch(photo)
        info['method_used'] = 'white_patch'
    else:  # gray_world (default)
        balanced, info = _white_balance_gray_world(photo)
        info['method_used'] = 'gray_world'

    return balanced, info


def _white_balance_gray_world(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Apply gray-world white balance.

    Assumes that the average color of the image should be gray (equal RGB values).
    Scales each channel so that their means are equal.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Tuple of (balanced image, info dict)
    """
    # Compute mean of each channel
    mean_r = np.mean(photo[:, :, 0])
    mean_g = np.mean(photo[:, :, 1])
    mean_b = np.mean(photo[:, :, 2])

    # Target is the overall gray level (average of channel means)
    target_gray = (mean_r + mean_g + mean_b) / 3.0

    # Avoid division by zero
    if mean_r < 0.001 or mean_g < 0.001 or mean_b < 0.001:
        logger.warning("Channel mean too low for white balance, passing through")
        return photo, {'gain_r': 1.0, 'gain_g': 1.0, 'gain_b': 1.0}

    # Compute gain factors to normalize each channel to target gray
    gain_r = target_gray / mean_r
    gain_g = target_gray / mean_g
    gain_b = target_gray / mean_b

    # Clamp gains to conservative range (±⅓ stop max — avoids destroying scene colors)
    gain_r = np.clip(gain_r, 0.75, 1.33)
    gain_g = np.clip(gain_g, 0.75, 1.33)
    gain_b = np.clip(gain_b, 0.75, 1.33)

    # Apply gains
    balanced = photo.copy()
    balanced[:, :, 0] = np.clip(balanced[:, :, 0] * gain_r, 0.0, 1.0)
    balanced[:, :, 1] = np.clip(balanced[:, :, 1] * gain_g, 0.0, 1.0)
    balanced[:, :, 2] = np.clip(balanced[:, :, 2] * gain_b, 0.0, 1.0)

    logger.debug(f"Gray-world WB gains: R={gain_r:.3f}, G={gain_g:.3f}, B={gain_b:.3f}")

    return balanced, {
        'gain_r': float(gain_r),
        'gain_g': float(gain_g),
        'gain_b': float(gain_b),
    }


def _white_balance_white_patch(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Apply white-patch white balance.

    Assumes the brightest pixels in the image should be white (RGB = 1.0).
    Uses the 99th percentile to avoid outliers.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Tuple of (balanced image, info dict)
    """
    # Find 99th percentile (bright pixels, but not extreme outliers)
    percentile = 99.0
    max_r = np.percentile(photo[:, :, 0], percentile)
    max_g = np.percentile(photo[:, :, 1], percentile)
    max_b = np.percentile(photo[:, :, 2], percentile)

    # Avoid division by zero
    if max_r < 0.1 or max_g < 0.1 or max_b < 0.1:
        logger.warning("Brightest pixels too dim for white-patch WB, falling back to gray-world")
        return _white_balance_gray_world(photo)

    # Compute gains to normalize bright pixels to 1.0
    gain_r = 1.0 / max_r
    gain_g = 1.0 / max_g
    gain_b = 1.0 / max_b

    # Clamp gains to conservative range (±⅓ stop max)
    gain_r = np.clip(gain_r, 0.75, 1.33)
    gain_g = np.clip(gain_g, 0.75, 1.33)
    gain_b = np.clip(gain_b, 0.75, 1.33)

    # Apply gains
    balanced = photo.copy()
    balanced[:, :, 0] = np.clip(balanced[:, :, 0] * gain_r, 0.0, 1.0)
    balanced[:, :, 1] = np.clip(balanced[:, :, 1] * gain_g, 0.0, 1.0)
    balanced[:, :, 2] = np.clip(balanced[:, :, 2] * gain_b, 0.0, 1.0)

    logger.debug(f"White-patch WB gains: R={gain_r:.3f}, G={gain_g:.3f}, B={gain_b:.3f}")

    return balanced, {
        'gain_r': float(gain_r),
        'gain_g': float(gain_g),
        'gain_b': float(gain_b),
    }


def _white_balance_from_reference(
    photo: np.ndarray,
    reference_pixels: np.ndarray
) -> Tuple[np.ndarray, dict]:
    """Apply white balance using reference pixels (e.g., album page border).

    Assumes the reference pixels (album page border) should be neutral gray/white.
    Computes gains to make the reference pixels neutral and applies to the whole image.

    Args:
        photo: Input image as float32 RGB [0, 1]
        reference_pixels: Reference pixels as float32 RGB [0, 1], shape (N, 3)

    Returns:
        Tuple of (balanced image, info dict)
    """
    # Compute mean of reference pixels
    ref_mean_r = np.mean(reference_pixels[:, 0])
    ref_mean_g = np.mean(reference_pixels[:, 1])
    ref_mean_b = np.mean(reference_pixels[:, 2])

    # Target is the average (should be neutral gray)
    target = (ref_mean_r + ref_mean_g + ref_mean_b) / 3.0

    # Avoid division by zero
    if ref_mean_r < 0.01 or ref_mean_g < 0.01 or ref_mean_b < 0.01:
        logger.warning("Reference pixels too dark, falling back to gray-world")
        return _white_balance_gray_world(photo)

    # Compute gains
    gain_r = target / ref_mean_r
    gain_g = target / ref_mean_g
    gain_b = target / ref_mean_b

    # Clamp gains to conservative range (±⅓ stop max)
    gain_r = np.clip(gain_r, 0.75, 1.33)
    gain_g = np.clip(gain_g, 0.75, 1.33)
    gain_b = np.clip(gain_b, 0.75, 1.33)

    # Apply gains
    balanced = photo.copy()
    balanced[:, :, 0] = np.clip(balanced[:, :, 0] * gain_r, 0.0, 1.0)
    balanced[:, :, 1] = np.clip(balanced[:, :, 1] * gain_g, 0.0, 1.0)
    balanced[:, :, 2] = np.clip(balanced[:, :, 2] * gain_b, 0.0, 1.0)

    logger.debug(f"Reference-based WB gains: R={gain_r:.3f}, G={gain_g:.3f}, B={gain_b:.3f}")

    return balanced, {
        'gain_r': float(gain_r),
        'gain_g': float(gain_g),
        'gain_b': float(gain_b),
    }


def assess_white_balance_quality(photo: np.ndarray) -> dict:
    """Assess whether a photo needs white balance correction.

    Returns metrics that indicate if the photo has a color cast.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Dict with 'color_cast_score' (0-1, higher = more cast),
        'dominant_cast' ('red', 'green', 'blue', 'yellow', 'cyan', 'magenta', or 'none')
    """
    # Compute channel means
    mean_r = np.mean(photo[:, :, 0])
    mean_g = np.mean(photo[:, :, 1])
    mean_b = np.mean(photo[:, :, 2])

    # Compute deviations from gray
    overall_mean = (mean_r + mean_g + mean_b) / 3.0
    dev_r = mean_r - overall_mean
    dev_g = mean_g - overall_mean
    dev_b = mean_b - overall_mean

    # Color cast score: max deviation
    color_cast_score = max(abs(dev_r), abs(dev_g), abs(dev_b)) / (overall_mean + 1e-6)

    # Determine dominant cast
    threshold = 0.02  # 2% deviation threshold
    if abs(dev_r) < threshold and abs(dev_g) < threshold and abs(dev_b) < threshold:
        dominant_cast = 'none'
    elif dev_r > max(dev_g, dev_b):
        dominant_cast = 'red'
    elif dev_g > max(dev_r, dev_b):
        dominant_cast = 'green'
    elif dev_b > max(dev_r, dev_g):
        dominant_cast = 'blue'
    elif dev_r > 0 and dev_g > 0:
        dominant_cast = 'yellow'
    elif dev_g > 0 and dev_b > 0:
        dominant_cast = 'cyan'
    elif dev_r > 0 and dev_b > 0:
        dominant_cast = 'magenta'
    else:
        dominant_cast = 'none'

    return {
        'color_cast_score': float(color_cast_score),
        'dominant_cast': dominant_cast,
        'channel_means': {
            'r': float(mean_r),
            'g': float(mean_g),
            'b': float(mean_b),
        }
    }
