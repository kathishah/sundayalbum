"""Keystone correction — per-photo perspective correction for tilted shots.

This module provides fine-grained perspective correction for individual photos
after they have been extracted from album pages.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def correct_keystone(
    photo: np.ndarray,
    corners: Optional[np.ndarray] = None,
    max_angle: float = 40.0,
) -> Tuple[np.ndarray, bool]:
    """Apply keystone correction to a photo.

    This function corrects perspective distortion in photos that were captured
    at an angle. If corners are not provided, it will attempt to detect the
    photo boundaries automatically.

    Args:
        photo: Photo image, float32 RGB [0, 1]
        corners: Optional 4-point array of corners in clockwise order from top-left
                 If None, will attempt auto-detection
        max_angle: Maximum perspective angle to correct (degrees), default 40.0

    Returns:
        Tuple of (corrected_photo, correction_applied)
        - corrected_photo: Perspective-corrected image, float32 RGB [0, 1]
        - correction_applied: True if correction was applied, False if skipped
    """
    h, w = photo.shape[:2]

    # If no corners provided, try to detect them
    if corners is None:
        corners = _detect_photo_corners(photo)
        if corners is None:
            logger.debug("No corners detected, skipping keystone correction")
            return photo, False

    # Check if correction is actually needed
    # If the photo is already very close to rectangular, skip correction
    if not _needs_correction(corners, max_angle):
        logger.debug("Photo already rectangular, skipping keystone correction")
        return photo, False

    # Compute target dimensions from corner distances
    target_width, target_height = _compute_target_dimensions(corners)

    # Ensure reasonable dimensions
    target_width = max(100, min(target_width, w * 2))
    target_height = max(100, min(target_height, h * 2))

    # Define destination corners (perfect rectangle)
    dst_corners = np.array([
        [0, 0],
        [target_width - 1, 0],
        [target_width - 1, target_height - 1],
        [0, target_height - 1],
    ], dtype=np.float32)

    # Compute perspective transform matrix
    # Convert to uint8 for cv2.warpPerspective
    photo_uint8 = (photo * 255).astype(np.uint8)

    # Ensure corners are float32
    src_corners = corners.astype(np.float32)

    try:
        # Compute homography
        M = cv2.getPerspectiveTransform(src_corners, dst_corners)

        # Apply perspective warp
        warped_uint8 = cv2.warpPerspective(
            photo_uint8,
            M,
            (target_width, target_height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),  # White border if needed
        )

        # Convert back to float32
        warped = warped_uint8.astype(np.float32) / 255.0

        logger.debug(
            f"Applied keystone correction: {w}x{h} → {target_width}x{target_height}"
        )
        return warped, True

    except cv2.error as e:
        logger.warning(f"Failed to apply keystone correction: {e}")
        return photo, False


def _detect_photo_corners(photo: np.ndarray) -> Optional[np.ndarray]:
    """Detect the 4 corners of the photo boundary.

    Args:
        photo: Photo image, float32 RGB [0, 1]

    Returns:
        4x2 array of corner points in clockwise order from top-left, or None
    """
    h, w = photo.shape[:2]

    # Convert to grayscale uint8
    gray = (photo.mean(axis=2) * 255).astype(np.uint8)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Find the largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest_contour)

    # Must be at least 30% of image area
    min_area = 0.3 * w * h
    if area < min_area:
        return None

    # Approximate to polygon
    epsilon = 0.02 * cv2.arcLength(largest_contour, True)
    approx = cv2.approxPolyDP(largest_contour, epsilon, True)

    # Must be a quadrilateral
    if len(approx) != 4:
        return None

    # Extract corners and order them
    corners = approx.reshape(4, 2).astype(np.float32)
    corners = _order_corners(corners)

    return corners


def _order_corners(corners: np.ndarray) -> np.ndarray:
    """Order corners in clockwise order from top-left.

    Args:
        corners: 4x2 array of corner points

    Returns:
        4x2 array of corners ordered: [top-left, top-right, bottom-right, bottom-left]
    """
    # Sort by y-coordinate to get top and bottom pairs
    sorted_by_y = corners[np.argsort(corners[:, 1])]
    top_pair = sorted_by_y[:2]
    bottom_pair = sorted_by_y[2:]

    # Within each pair, sort by x-coordinate
    top_left, top_right = top_pair[np.argsort(top_pair[:, 0])]
    bottom_left, bottom_right = bottom_pair[np.argsort(bottom_pair[:, 0])]

    return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)


def _needs_correction(corners: np.ndarray, max_angle: float) -> bool:
    """Check if the photo needs perspective correction.

    Args:
        corners: 4x2 array of corner points
        max_angle: Maximum angle threshold (degrees)

    Returns:
        True if correction is needed, False otherwise
    """
    # Compute angles at each corner
    angles = []
    for i in range(4):
        p1 = corners[i]
        p2 = corners[(i + 1) % 4]
        p0 = corners[(i - 1) % 4]

        # Vectors from p1 to adjacent corners
        v1 = p0 - p1
        v2 = p2 - p1

        # Compute angle
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        angle_rad = np.arccos(np.clip(cos_angle, -1.0, 1.0))
        angle_deg = np.degrees(angle_rad)

        # Deviation from 90 degrees
        deviation = abs(angle_deg - 90.0)
        angles.append(deviation)

    # If any corner deviates more than a threshold, correction is needed
    max_deviation = max(angles)
    needs_correction = max_deviation > 5.0  # 5 degree tolerance

    logger.debug(f"Corner angle deviations: {[f'{a:.1f}°' for a in angles]}, "
                 f"max: {max_deviation:.1f}°, needs_correction: {needs_correction}")

    return needs_correction


def _compute_target_dimensions(corners: np.ndarray) -> Tuple[int, int]:
    """Compute target dimensions for the corrected photo.

    Args:
        corners: 4x2 array of corner points in clockwise order

    Returns:
        Tuple of (width, height) for the corrected image
    """
    # Width: average of top and bottom edge lengths
    top_width = np.linalg.norm(corners[1] - corners[0])
    bottom_width = np.linalg.norm(corners[2] - corners[3])

    # Height: average of left and right edge lengths
    left_height = np.linalg.norm(corners[3] - corners[0])
    right_height = np.linalg.norm(corners[2] - corners[1])

    target_width = int((top_width + bottom_width) / 2)
    target_height = int((left_height + right_height) / 2)

    return target_width, target_height
