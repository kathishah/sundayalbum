"""Rotation correction — detect and fix rotation errors in photos.

This module detects and corrects both small rotation errors (±15°) from angled
captures and large 90°/180° orientation errors.
"""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def correct_rotation(
    photo: np.ndarray,
    auto_correct_max: float = 15.0,
) -> Tuple[np.ndarray, float]:
    """Detect and correct rotation in a photo.

    This function handles two types of rotation:
    1. Small rotations (±auto_correct_max degrees) from slightly angled captures
    2. Large 90°/180° orientation errors

    Args:
        photo: Photo image, float32 RGB [0, 1]
        auto_correct_max: Maximum angle to auto-correct (degrees), default 15.0

    Returns:
        Tuple of (corrected_photo, rotation_angle)
        - corrected_photo: Rotation-corrected image, float32 RGB [0, 1]
        - rotation_angle: Applied rotation in degrees (positive = clockwise)
    """
    # First, detect small rotations using dominant line analysis
    small_angle = _detect_small_rotation(photo, auto_correct_max)

    # Apply small rotation if detected
    if abs(small_angle) > 0.5:  # Only correct if > 0.5 degrees
        photo = _rotate_image(photo, small_angle)
        logger.debug(f"Applied small rotation correction: {small_angle:.2f}°")
    else:
        small_angle = 0.0

    # Then check for 90°/180° orientation errors
    orientation_angle = _detect_orientation_error(photo)

    # Apply orientation correction if detected
    if orientation_angle != 0:
        photo = _rotate_image(photo, orientation_angle)
        logger.debug(f"Applied orientation correction: {orientation_angle}°")

    total_angle = small_angle + orientation_angle

    if total_angle != 0:
        logger.info(f"Total rotation applied: {total_angle:.2f}°")

    return photo, total_angle


def _detect_small_rotation(photo: np.ndarray, max_angle: float) -> float:
    """Detect small rotation angle using dominant line analysis.

    Uses Hough line transform to find dominant lines in the image, then
    computes the median angle deviation from horizontal/vertical.

    NOTE: Disabled — returns 0.0 unconditionally. The Hough transform fires
    on image *content* (car bodies, boat rigging, rock edges) rather than the
    photo frame, producing false corrections that tilt already-correct images.
    Gross orientation errors (90°/180°/270°) are handled by the AI orientation
    step (Step 4.5). Fine-drift correction should use the photo's white border
    or detected corner quadrilateral, not content lines.

    Args:
        photo: Photo image, float32 RGB [0, 1]
        max_angle: Maximum angle to detect (degrees)

    Returns:
        Rotation angle in degrees (positive = clockwise)
    """
    return 0.0

    # --- disabled code below ---
    h, w = photo.shape[:2]

    # Convert to grayscale uint8
    gray = (photo.mean(axis=2) * 255).astype(np.uint8)

    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Hough line transform
    # Use probabilistic Hough transform for efficiency
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=min(w, h) // 4,  # Lines must be at least 1/4 image size
        maxLineGap=20,
    )

    if lines is None or len(lines) < 5:
        logger.debug("Not enough lines detected for rotation analysis")
        return 0.0

    # Compute angles for all detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        # Skip very short lines
        length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        if length < 50:
            continue

        # Compute angle relative to horizontal
        angle_rad = np.arctan2(y2 - y1, x2 - x1)
        angle_deg = np.degrees(angle_rad)

        # Normalize to [-45, 45] range
        # (we want deviation from nearest horizontal/vertical axis)
        while angle_deg > 45:
            angle_deg -= 90
        while angle_deg < -45:
            angle_deg += 90

        angles.append(angle_deg)

    if not angles:
        return 0.0

    # Use median angle to avoid outliers
    median_angle = np.median(angles)

    # Only correct if within max_angle threshold
    if abs(median_angle) > max_angle:
        logger.debug(
            f"Detected rotation {median_angle:.2f}° exceeds max {max_angle}°, skipping"
        )
        return 0.0

    # Also ignore very small rotations (likely noise)
    if abs(median_angle) < 0.5:
        return 0.0

    logger.debug(f"Detected small rotation: {median_angle:.2f}° (from {len(angles)} lines)")

    return -median_angle  # Negative because we want to correct (rotate back)


def _detect_orientation_error(photo: np.ndarray) -> float:
    """Detect 90° or 180° orientation errors.

    Uses simple heuristics based on image content:
    - Check aspect ratio (portrait vs landscape)
    - Analyze intensity distribution (sky should be at top)
    - Check for text orientation (if detectable)

    Args:
        photo: Photo image, float32 RGB [0, 1]

    Returns:
        Correction angle: 0, 90, 180, or 270 degrees
    """
    h, w = photo.shape[:2]

    # Simple heuristic: check if sky (bright regions) are at the top
    # This works for many outdoor photos
    top_third = photo[:h//3, :, :]
    bottom_third = photo[2*h//3:, :, :]

    top_brightness = top_third.mean()
    bottom_brightness = bottom_third.mean()

    # If bottom is significantly brighter than top, photo might be upside down
    # Use a conservative threshold to avoid false positives
    brightness_ratio = bottom_brightness / (top_brightness + 1e-6)

    if brightness_ratio > 1.3:  # Bottom is 30% brighter
        logger.debug(
            f"Possible 180° orientation error detected "
            f"(bottom brightness: {bottom_brightness:.3f}, top: {top_brightness:.3f})"
        )
        # Conservative: don't auto-rotate 180° without more evidence
        # This would need face detection or other semantic understanding
        return 0.0

    # For 90° rotation detection, we'd need more sophisticated analysis
    # (text detection, face detection, semantic segmentation)
    # For now, skip 90° auto-correction to avoid false positives

    return 0.0


def _rotate_image(photo: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image by the given angle.

    Args:
        photo: Photo image, float32 RGB [0, 1]
        angle: Rotation angle in degrees (positive = clockwise)

    Returns:
        Rotated image, float32 RGB [0, 1]
    """
    h, w = photo.shape[:2]

    # Handle 90° multiples separately (faster and no interpolation artifacts)
    if angle % 90 == 0:
        k = int(angle // 90) % 4
        if k == 0:
            return photo
        elif k == 1:  # 90° clockwise
            return np.rot90(photo, k=3)  # rot90 is counter-clockwise, so k=3 for clockwise
        elif k == 2:  # 180°
            return np.rot90(photo, k=2)
        else:  # 270° clockwise = 90° counter-clockwise
            return np.rot90(photo, k=1)

    # For arbitrary angles, use affine transform
    # Convert to uint8
    photo_uint8 = (photo * 255).astype(np.uint8)

    # Compute rotation matrix (around image center)
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, -angle, scale=1.0)  # Negative for clockwise

    # Compute new bounding box size to avoid cropping
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    # Adjust the rotation matrix to account for translation
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    # Apply rotation
    rotated_uint8 = cv2.warpAffine(
        photo_uint8,
        M,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    # Convert back to float32
    rotated = rotated_uint8.astype(np.float32) / 255.0

    return rotated
