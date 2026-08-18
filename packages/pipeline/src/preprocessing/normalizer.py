"""Image normalization module for resizing and thumbnail generation."""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class NormalizationResult:
    """Result of image normalization."""

    def __init__(
        self,
        image: np.ndarray,
        thumbnail: np.ndarray,
        scale_factor: float
    ) -> None:
        self.image = image
        self.thumbnail = thumbnail
        self.scale_factor = scale_factor


def normalize(
    image: np.ndarray,
    max_working_resolution: int = 4000,
    thumbnail_size: int = 400
) -> NormalizationResult:
    """Normalize image by resizing to working resolution and generating thumbnail.

    Args:
        image: Input image as float32 RGB [0,1] array
        max_working_resolution: Maximum dimension (width or height) for working image
        thumbnail_size: Maximum dimension for thumbnail

    Returns:
        NormalizationResult with normalized image, thumbnail, and scale factor
    """
    height, width = image.shape[:2]
    original_max_dim = max(height, width)

    # Calculate scale factor for working resolution
    if original_max_dim > max_working_resolution:
        scale_factor = max_working_resolution / original_max_dim
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        # Convert to uint8 for OpenCV resize
        img_uint8 = (image * 255).astype(np.uint8)

        # Resize using INTER_AREA (best for downscaling)
        resized_uint8 = cv2.resize(
            img_uint8,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA
        )

        # Convert back to float32
        normalized_image = resized_uint8.astype(np.float32) / 255.0

        logger.info(
            f"Resized image from {width}x{height} to {new_width}x{new_height} "
            f"(scale: {scale_factor:.3f})"
        )
    else:
        normalized_image = image
        scale_factor = 1.0
        logger.info(f"Image {width}x{height} within working resolution, no resize needed")

    # Generate thumbnail
    current_height, current_width = normalized_image.shape[:2]
    current_max_dim = max(current_height, current_width)
    thumb_scale = thumbnail_size / current_max_dim

    thumb_width = int(current_width * thumb_scale)
    thumb_height = int(current_height * thumb_scale)

    # Convert to uint8 for OpenCV resize
    img_uint8 = (normalized_image * 255).astype(np.uint8)

    thumbnail_uint8 = cv2.resize(
        img_uint8,
        (thumb_width, thumb_height),
        interpolation=cv2.INTER_AREA
    )

    thumbnail = thumbnail_uint8.astype(np.float32) / 255.0

    logger.debug(f"Generated thumbnail: {thumb_width}x{thumb_height}")

    return NormalizationResult(
        image=normalized_image,
        thumbnail=thumbnail,
        scale_factor=scale_factor
    )
