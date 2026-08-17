"""Final enhancement and sharpening for photo restoration.

This module applies final touches to restored photos: sharpening using unsharp
mask and subtle contrast enhancement using sigmoid tone curves. Always conservative
to maintain natural appearance.
"""

import logging
from typing import Tuple, Optional

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter

logger = logging.getLogger(__name__)


def enhance(
    photo: np.ndarray,
    sharpen_radius: float = 1.5,
    sharpen_amount: float = 0.5,
    apply_contrast: bool = True,
    contrast_strength: float = 0.15
) -> Tuple[np.ndarray, dict]:
    """Apply final enhancement: sharpening and subtle contrast adjustment.

    Works on the L channel in LAB space to avoid color artifacts.
    Uses unsharp mask for sharpening and sigmoid tone curve for contrast.

    Args:
        photo: Input image as float32 RGB [0, 1], shape (H, W, 3)
        sharpen_radius: Gaussian blur radius for unsharp mask (pixels)
        sharpen_amount: Sharpening strength (0.0 = none, 1.0 = strong)
        apply_contrast: Whether to apply sigmoid tone curve for contrast
        contrast_strength: Strength of contrast enhancement (0.0-1.0)

    Returns:
        Tuple of:
            - Enhanced image as float32 RGB [0, 1]
            - Info dict with enhancement metrics
    """
    if photo.ndim != 3 or photo.shape[2] != 3:
        logger.warning(f"Invalid photo shape: {photo.shape}, expected (H, W, 3)")
        return photo, {'error': 'invalid_shape'}

    # Convert to LAB to work on L channel only (avoid color artifacts)
    photo_uint8 = (photo * 255).astype(np.uint8)
    lab = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2LAB).astype(np.float32)

    L = lab[:, :, 0]  # Lightness: 0-100 (OpenCV uses 0-255 scale)
    a = lab[:, :, 1]
    b = lab[:, :, 2]

    # Measure sharpness before enhancement
    sharpness_before = measure_sharpness(L.astype(np.uint8))

    # Apply sharpening to L channel
    if sharpen_amount > 0.0:
        L_sharpened = _unsharp_mask(L, radius=sharpen_radius, amount=sharpen_amount)
    else:
        L_sharpened = L

    # Apply contrast enhancement to L channel
    if apply_contrast and contrast_strength > 0.0:
        L_enhanced = _apply_sigmoid_contrast(L_sharpened, strength=contrast_strength)
    else:
        L_enhanced = L_sharpened

    # Measure sharpness after enhancement
    sharpness_after = measure_sharpness(L_enhanced.astype(np.uint8))
    sharpness_improvement = sharpness_after / (sharpness_before + 1e-6)

    logger.debug(
        f"Enhancement applied: sharpness {sharpness_before:.2f} → {sharpness_after:.2f} "
        f"({sharpness_improvement:.2f}x)"
    )

    # Reconstruct LAB image
    lab_enhanced = lab.copy()
    lab_enhanced[:, :, 0] = L_enhanced

    # Convert back to RGB
    lab_enhanced_uint8 = np.clip(lab_enhanced, 0, 255).astype(np.uint8)
    rgb_enhanced_uint8 = cv2.cvtColor(lab_enhanced_uint8, cv2.COLOR_LAB2RGB)
    rgb_enhanced = rgb_enhanced_uint8.astype(np.float32) / 255.0

    logger.info(
        f"Enhancement complete: sharpness improved {sharpness_improvement:.2f}x, "
        f"sharpen={sharpen_amount:.2f}, contrast={contrast_strength:.2f}"
    )

    return rgb_enhanced, {
        'sharpness_before': float(sharpness_before),
        'sharpness_after': float(sharpness_after),
        'sharpness_improvement': float(sharpness_improvement),
        'sharpen_amount': float(sharpen_amount),
        'contrast_strength': float(contrast_strength),
    }


def _unsharp_mask(
    image: np.ndarray,
    radius: float = 1.5,
    amount: float = 0.5
) -> np.ndarray:
    """Apply unsharp mask sharpening.

    Unsharp mask: sharp = original + amount * (original - blurred)

    Args:
        image: Input image (single channel, float32)
        radius: Gaussian blur radius in pixels
        amount: Sharpening strength

    Returns:
        Sharpened image (same type as input)
    """
    # Create blurred version
    blurred = gaussian_filter(image, sigma=radius)

    # Compute high-frequency detail
    detail = image - blurred

    # Add detail back to original
    sharpened = image + amount * detail

    # Clip to valid range
    sharpened = np.clip(sharpened, 0, 255)

    return sharpened


def _apply_sigmoid_contrast(
    image: np.ndarray,
    strength: float = 0.15,
    midpoint: float = 127.5
) -> np.ndarray:
    """Apply sigmoid tone curve for subtle contrast enhancement.

    Sigmoid curve: S-shaped, increases contrast in mid-tones while
    preserving highlights and shadows (avoids clipping).

    Args:
        image: Input image (single channel, float32, 0-255 range)
        strength: Strength of contrast enhancement (0.0-1.0)
        midpoint: Center point of the curve (usually middle gray)

    Returns:
        Image with enhanced contrast (same type as input)
    """
    if strength <= 0.0:
        return image

    # Normalize to 0-1 range
    img_normalized = image / 255.0

    # Sigmoid parameters
    # Higher gain = more contrast
    gain = 5.0 * strength  # Map 0-1 strength to 0-5 gain

    # Apply sigmoid: y = 1 / (1 + exp(-gain * (x - 0.5)))
    # This creates an S-curve centered at 0.5 (mid-gray)
    sigmoid = 1.0 / (1.0 + np.exp(-gain * (img_normalized - 0.5)))

    # Blend with original based on strength
    # (This gives us finer control and ensures subtle enhancement)
    enhanced_normalized = img_normalized * (1.0 - strength) + sigmoid * strength

    # Scale back to 0-255
    enhanced = enhanced_normalized * 255.0

    # Clip to valid range
    enhanced = np.clip(enhanced, 0, 255)

    return enhanced


def measure_sharpness(image: np.ndarray) -> float:
    """Measure image sharpness using Laplacian variance.

    Higher values indicate sharper images (more high-frequency detail).

    Args:
        image: Input image (single channel, uint8 or float32)

    Returns:
        Sharpness score (higher = sharper)
    """
    # Convert to uint8 if needed
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)

    # Compute Laplacian (detects edges/high-frequency content)
    laplacian = cv2.Laplacian(image, cv2.CV_64F)

    # Variance of Laplacian is a measure of sharpness
    sharpness = float(laplacian.var())

    return sharpness


def assess_enhancement_need(photo: np.ndarray) -> dict:
    """Assess whether a photo needs sharpening and contrast enhancement.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Dict with 'needs_sharpening', 'needs_contrast', 'sharpness_score',
        'contrast_score', and 'recommended_sharpen_amount'
    """
    # Convert to grayscale for analysis
    photo_uint8 = (photo * 255).astype(np.uint8)
    gray = cv2.cvtColor(photo_uint8, cv2.COLOR_RGB2GRAY)

    # Measure sharpness
    sharpness = measure_sharpness(gray)
    # Typical sharp photos: sharpness > 200
    # Blurry photos: sharpness < 100
    needs_sharpening = sharpness < 150
    normalized_sharpness = min(1.0, sharpness / 200.0)

    # Compute local contrast (standard deviation)
    local_contrast = float(np.std(gray))
    # Typical good contrast: std > 40
    # Low contrast: std < 25
    needs_contrast = local_contrast < 30
    normalized_contrast = min(1.0, local_contrast / 50.0)

    # Recommend sharpening amount based on sharpness deficit
    if needs_sharpening:
        sharpen_deficit = 1.0 - normalized_sharpness
        recommended_sharpen = 0.3 + 0.4 * sharpen_deficit  # 0.3-0.7 range
    else:
        recommended_sharpen = 0.2  # Minimal sharpening for already-sharp photos

    logger.debug(
        f"Enhancement assessment: sharpness={sharpness:.1f} "
        f"(needs_sharpen={needs_sharpening}), "
        f"contrast={local_contrast:.1f} (needs_contrast={needs_contrast})"
    )

    return {
        'needs_sharpening': bool(needs_sharpening),
        'needs_contrast': bool(needs_contrast),
        'sharpness_score': float(sharpness),
        'normalized_sharpness': float(normalized_sharpness),
        'contrast_score': float(local_contrast),
        'normalized_contrast': float(normalized_contrast),
        'recommended_sharpen_amount': float(recommended_sharpen),
    }


def enhance_adaptive(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Apply enhancement with adaptive parameters based on photo analysis.

    Automatically determines optimal sharpening and contrast settings.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Tuple of (enhanced image, info dict)
    """
    # Assess photo
    assessment = assess_enhancement_need(photo)

    # Determine parameters
    sharpen_amount = assessment['recommended_sharpen_amount']

    if assessment['needs_contrast']:
        contrast_strength = 0.2
    else:
        contrast_strength = 0.1  # Subtle contrast for already good photos

    # Apply enhancement
    enhanced, info = enhance(
        photo,
        sharpen_radius=1.5,
        sharpen_amount=sharpen_amount,
        apply_contrast=True,
        contrast_strength=contrast_strength
    )

    # Add assessment info
    info['assessment'] = assessment

    return enhanced, info


def enhance_conservative(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Apply very subtle enhancement to avoid over-processing.

    Good for already good-quality photos that just need a light touch.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Tuple of (enhanced image, info dict)
    """
    return enhance(
        photo,
        sharpen_radius=1.0,
        sharpen_amount=0.25,  # Very light
        apply_contrast=True,
        contrast_strength=0.05  # Very subtle
    )


def enhance_aggressive(photo: np.ndarray) -> Tuple[np.ndarray, dict]:
    """Apply strong enhancement for blurry or low-contrast photos.

    Use with caution - can introduce artifacts if applied to already-sharp photos.

    Args:
        photo: Input image as float32 RGB [0, 1]

    Returns:
        Tuple of (enhanced image, info dict)
    """
    return enhance(
        photo,
        sharpen_radius=2.0,
        sharpen_amount=0.8,  # Strong
        apply_contrast=True,
        contrast_strength=0.3  # Strong
    )
