"""Photo splitting — extract individual photos from album pages."""

import logging
from typing import List

import cv2
import numpy as np

from src.photo_detection.detector import PhotoDetection

logger = logging.getLogger(__name__)


def split_photos(
    page_image: np.ndarray,
    detections: List[PhotoDetection],
) -> List[np.ndarray]:
    """Extract individual photos from the page based on detections.

    Each detected photo is cropped and perspective-corrected if needed.

    Args:
        page_image: Album page image, float32 RGB [0, 1]
        detections: List of PhotoDetection objects

    Returns:
        List of extracted photo images, float32 RGB [0, 1]
    """
    extracted_photos: List[np.ndarray] = []

    for i, detection in enumerate(detections):
        try:
            # Extract and correct this photo
            photo = _extract_single_photo(page_image, detection)
            extracted_photos.append(photo)
            logger.debug(f"Extracted photo {i+1}: shape {photo.shape}")

        except Exception as e:
            logger.warning(f"Failed to extract photo {i+1}: {e}")
            continue

    logger.info(f"Successfully extracted {len(extracted_photos)}/{len(detections)} photos")

    return extracted_photos


def _extract_single_photo(
    page_image: np.ndarray,
    detection: PhotoDetection,
) -> np.ndarray:
    """Extract and perspective-correct a single photo.

    Args:
        page_image: Album page image, float32 RGB [0, 1]
        detection: Photo detection information

    Returns:
        Extracted photo image, float32 RGB [0, 1]
    """
    h, w = page_image.shape[:2]

    # Check if perspective correction is needed
    # If corners are already very close to a perfect rectangle, skip correction
    corners = detection.corners

    # Compute target dimensions from corner distances
    # Width: average of top and bottom edge lengths
    # Height: average of left and right edge lengths
    top_width = np.linalg.norm(corners[1] - corners[0])
    bottom_width = np.linalg.norm(corners[2] - corners[3])
    left_height = np.linalg.norm(corners[3] - corners[0])
    right_height = np.linalg.norm(corners[2] - corners[1])

    target_width = int((top_width + bottom_width) / 2)
    target_height = int((left_height + right_height) / 2)

    # Ensure reasonable dimensions
    target_width = max(100, min(target_width, w))
    target_height = max(100, min(target_height, h))

    # Define destination corners (perfect rectangle)
    dst_corners = np.array([
        [0, 0],
        [target_width - 1, 0],
        [target_width - 1, target_height - 1],
        [0, target_height - 1],
    ], dtype=np.float32)

    # Compute perspective transform matrix
    # Convert to uint8 for cv2.warpPerspective
    image_uint8 = (page_image * 255).astype(np.uint8)

    # Ensure corners are float32
    src_corners = corners.astype(np.float32)

    # Compute homography
    M = cv2.getPerspectiveTransform(src_corners, dst_corners)

    # Apply perspective warp
    warped_uint8 = cv2.warpPerspective(
        image_uint8,
        M,
        (target_width, target_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),  # White border if needed
    )

    # Convert back to float32
    warped = warped_uint8.astype(np.float32) / 255.0

    return warped
