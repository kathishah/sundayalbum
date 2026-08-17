"""Region classifier — distinguish photos from decorations, captions, etc."""

import logging
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)


RegionType = Literal["photo", "decoration", "caption", "unknown"]


def classify_region(
    region_image: np.ndarray,
    bbox_area: float,
    page_area: float,
) -> RegionType:
    """Classify a detected region as photo, decoration, caption, etc.

    This is a simple heuristic classifier. For now, we assume most detected
    regions are photos. Future enhancements could use color analysis, texture,
    or ML models.

    Args:
        region_image: The extracted region, float32 RGB [0, 1]
        bbox_area: Area of the region's bounding box
        page_area: Total area of the page

    Returns:
        Region type classification
    """
    # Check aspect ratio first - elongated regions are likely captions
    # even if they're small
    h, w = region_image.shape[:2]
    aspect_ratio = max(w, h) / (min(w, h) + 1e-6)

    # Extremely elongated regions might be captions or borders
    if aspect_ratio > 8.0:
        return "caption"

    # Area ratio relative to page
    area_ratio = bbox_area / page_area

    # Very small regions (< 2% of page) are likely decorations
    if area_ratio < 0.02:
        return "decoration"

    # Color variance check — photos typically have varied colors
    # Decorations might be more uniform
    std_dev = np.std(region_image)

    if std_dev < 0.05:  # Very low variance
        return "decoration"

    # Default: assume it's a photo
    return "photo"
