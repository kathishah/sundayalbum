"""Yellowing removal for aged photo restoration.

This module removes the yellow/brown cast that develops in old photos due to
aging of the paper and chemicals. Works in LAB color space to adjust the
blue-yellow (b*) channel.
"""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def remove_yellowing(
    photo: np.ndarray,
    strength: float = 0.5,
    auto_detect: bool = True
) -> Tuple[np.ndarray, dict]:
    """Remove yellowing from aged photos.

    Detects and corrects yellow/brown color casts that develop in old photos.
    Works in LAB color space by adjusting the b* channel (blue-yellow axis).
    Conservative approach to avoid removing intentional warm tones.

    Args:
        photo: Input image as float32 RGB [0, 1], shape (H, W, 3)
        strength: Correction strength, 0.0 = no correction, 1.0 = full correction
        auto_detect: If True, only correct if significant yellowing detected

    Returns:
        Tuple of:
            - Corrected image as float32 RGB [0, 1]
            - Info dict with 'yellowing_score', 'shift_applied', 'corrected'
    """
    if photo.ndim != 3 or photo.shape[2] != 3:
        logger.warning(f"Invalid photo shape: {photo.shape}, expected (H, W, 3)")
        return photo, {'error': 'invalid_shape', 'corrected': False}

    # Convert to LAB color space (scaled 0-100, -128 to 127, -128 to 127)
    photo_uint8 = (photo * 255).astype(np.uint8)
    lab = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2LAB).astype(np.float32)

    # Extract L, a, b channels
    L = lab[:, :, 0]  # Lightness: 0-100
    a = lab[:, :, 1]  # Green-Red: 0-255 (128 is neutral)
    b = lab[:, :, 2]  # Blue-Yellow: 0-255 (128 is neutral)

    # Convert b* from 0-255 scale to -128 to 127 scale (OpenCV uses 0-255)
    b_centered = b - 128.0

    # Compute yellowing metrics
    yellowing_info = _assess_yellowing(b_centered)
    yellowing_score = yellowing_info['yellowing_score']
    mean_b = yellowing_info['mean_b_shift']

    logger.debug(
        f"Yellowing detected: score={yellowing_score:.3f}, "
        f"mean b*={mean_b:.2f}, "
        f"median={yellowing_info['median_b_shift']:.2f}"
    )

    # Decide whether to correct
    if auto_detect and yellowing_score < 0.15:
        logger.debug("Yellowing below threshold, skipping correction")
        return photo, {
            'yellowing_score': float(yellowing_score),
            'shift_applied': 0.0,
            'corrected': False,
            'reason': 'below_threshold'
        }

    # Compute correction shift
    # We want to shift the b* distribution toward neutral (0)
    # Use the median as target (more robust to outliers than mean)
    target_shift = yellowing_info['median_b_shift']

    # Be conservative: don't shift all the way to neutral
    # This preserves intentional warm tones (sunset, golden hour, etc.)
    correction_shift = -target_shift * strength

    # Additional safety: limit the maximum shift
    max_shift = 20.0  # Don't shift more than 20 units in LAB b* space
    correction_shift = np.clip(correction_shift, -max_shift, max_shift)

    # Apply shift to b* channel
    b_corrected = b_centered + correction_shift

    # Clip to valid range
    b_corrected = np.clip(b_corrected, -128, 127)

    # Convert back to 0-255 scale
    b_corrected_uint8 = b_corrected + 128.0

    # Reconstruct LAB image
    lab_corrected = lab.copy()
    lab_corrected[:, :, 2] = b_corrected_uint8

    # Convert back to RGB
    lab_corrected_uint8 = np.clip(lab_corrected, 0, 255).astype(np.uint8)
    rgb_corrected_uint8 = cv2.cvtColor(lab_corrected_uint8, cv2.COLOR_LAB2RGB)
    rgb_corrected = rgb_corrected_uint8.astype(np.float32) / 255.0

    logger.info(
        f"Yellowing correction applied: shift={correction_shift:.2f}, "
        f"score={yellowing_score:.3f}"
    )

    return rgb_corrected, {
        'yellowing_score': float(yellowing_score),
        'shift_applied': float(correction_shift),
        'corrected': True,
        'mean_b_before': float(mean_b),
        'mean_b_after': float(np.mean(b_corrected)),
    }


def _assess_yellowing(b_channel: np.ndarray) -> dict:
    """Assess the degree of yellowing in a photo.

    Args:
        b_channel: The b* channel from LAB, centered at 0 (-128 to 127 range)

    Returns:
        Dict with yellowing metrics
    """
    # Compute statistics
    mean_b = np.mean(b_channel)
    median_b = np.median(b_channel)
    std_b = np.std(b_channel)

    # Yellowing score: how much the distribution is shifted toward yellow (positive b*)
    # Normalize by typical range (±50 is a strong color cast)
    yellowing_score = max(0.0, mean_b / 50.0)

    # Check histogram skew - yellowing shifts the whole distribution
    histogram, bin_edges = np.histogram(b_channel, bins=50, range=(-50, 50))
    histogram_normalized = histogram / (np.sum(histogram) + 1e-6)

    # Compute center of mass of histogram
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    histogram_center = np.sum(bin_centers * histogram_normalized)

    return {
        'yellowing_score': float(yellowing_score),
        'mean_b_shift': float(mean_b),
        'median_b_shift': float(median_b),
        'std_b': float(std_b),
        'histogram_center': float(histogram_center),
    }


def detect_intentional_warmth(photo: np.ndarray) -> dict:
    """Detect if a photo has intentional warm tones (sunset, golden hour, etc.).

    This helps avoid removing desirable warm color grading when correcting yellowing.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Dict with 'has_intentional_warmth' (bool) and 'confidence' (float 0-1)
    """
    # Convert to HSV to analyze hue distribution
    photo_uint8 = (photo * 255).astype(np.uint8)
    hsv = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2HSV)

    h = hsv[:, :, 0].astype(np.float32)  # Hue: 0-180
    s = hsv[:, :, 1].astype(np.float32) / 255.0  # Saturation: 0-1
    v = hsv[:, :, 2].astype(np.float32) / 255.0  # Value: 0-1

    # Warm hues in OpenCV HSV: 0-30 (red-orange-yellow)
    # Select pixels with warm hues and reasonable saturation
    warm_hue_mask = (h < 30) & (s > 0.2) & (v > 0.2)
    warm_pixel_ratio = np.sum(warm_hue_mask) / (photo.shape[0] * photo.shape[1])

    # High ratio of warm, saturated pixels suggests intentional warm tones.
    # Threshold lowered to 0.2 so scenes with moderate warmth (caves, candlelight)
    # are protected, not just full-frame sunset shots.
    has_intentional_warmth = warm_pixel_ratio > 0.2
    confidence = float(min(1.0, warm_pixel_ratio / 0.2))

    logger.debug(
        f"Intentional warmth detection: ratio={warm_pixel_ratio:.3f}, "
        f"has_warmth={has_intentional_warmth}, confidence={confidence:.3f}"
    )

    return {
        'has_intentional_warmth': has_intentional_warmth,
        'confidence': confidence,
        'warm_pixel_ratio': float(warm_pixel_ratio),
    }


def remove_yellowing_adaptive(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Remove yellowing with adaptive strength based on intentional warmth detection.

    Automatically adjusts correction strength to preserve intentional warm tones
    while removing age-related yellowing.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Tuple of (corrected image, info dict)
    """
    # Detect intentional warmth
    warmth_info = detect_intentional_warmth(photo)

    # Adjust strength based on warmth detection
    if warmth_info['has_intentional_warmth']:
        # Reduce correction strength for photos with intentional warm tones
        strength = 0.3 * (1.0 - warmth_info['confidence'] * 0.5)
        logger.info(
            f"Intentional warmth detected (confidence={warmth_info['confidence']:.2f}), "
            f"reducing deyellow strength to {strength:.2f}"
        )
    else:
        # Moderate strength for photos without warm tones.
        # Reduced from 0.6 to avoid over-correcting scenes with subtle warmth
        # that didn't cross the detection threshold.
        strength = 0.4

    # Apply yellowing removal with adjusted strength
    corrected, info = remove_yellowing(photo, strength=strength, auto_detect=True)

    # Add warmth detection info to result
    info['warmth_detection'] = warmth_info

    return corrected, info
