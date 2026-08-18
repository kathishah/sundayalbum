"""Perspective correction via homographic transform.

Takes detected page corners and warps the image to a fronto-parallel rectangle.
"""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _compute_output_dimensions(corners: np.ndarray) -> Tuple[int, int]:
    """Compute output rectangle dimensions from corner points.

    Uses the maximum of opposite edge lengths to determine width and height,
    preserving the page's natural aspect ratio.

    Args:
        corners: Ordered corner points (4, 2) as [TL, TR, BR, BL].

    Returns:
        (width, height) in pixels.
    """
    tl, tr, br, bl = corners

    # Width: average of top and bottom edge lengths
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    width = int(max(width_top, width_bottom))

    # Height: average of left and right edge lengths
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    height = int(max(height_left, height_right))

    return width, height


def correct_perspective(
    image: np.ndarray,
    corners: np.ndarray,
) -> np.ndarray:
    """Apply homographic transform to correct perspective distortion.

    Warps the region defined by corners to a proper rectangle.

    Args:
        image: Input image as float32 RGB [0, 1], shape (H, W, 3).
        corners: Ordered corner points (4, 2) as [TL, TR, BR, BL] in float32.

    Returns:
        Perspective-corrected image as float32 RGB [0, 1].
    """
    width, height = _compute_output_dimensions(corners)

    if width <= 0 or height <= 0:
        logger.warning("Invalid output dimensions from corners, returning input unchanged")
        return image

    # Define destination rectangle
    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1],
    ], dtype=np.float32)

    # Compute homography matrix
    matrix = cv2.getPerspectiveTransform(corners, dst)

    # Convert to uint8 for warping (better interpolation behavior)
    img_uint8 = (image * 255).astype(np.uint8)

    # Apply perspective warp
    warped_uint8 = cv2.warpPerspective(
        img_uint8,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    # Convert back to float32
    warped = warped_uint8.astype(np.float32) / 255.0

    logger.info(
        f"Perspective corrected: {image.shape[1]}x{image.shape[0]} -> {width}x{height}"
    )

    return warped
