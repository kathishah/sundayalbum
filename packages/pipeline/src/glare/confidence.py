"""Glare removal confidence scoring."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def compute_glare_confidence(original: np.ndarray, glare_mask: np.ndarray) -> float:
    """Compute confidence score for glare detection/removal.

    Higher score = better quality (less glare, or glare successfully handled).
    Lower score = more problematic glare.

    Args:
        original: Original image, float32 RGB [0, 1], shape (H, W, 3)
        glare_mask: Binary glare mask, uint8, 255 = glare

    Returns:
        Confidence score [0, 1]
        - 1.0: no glare detected, perfect
        - 0.8-0.99: minimal glare, easy to handle
        - 0.5-0.8: moderate glare, requires good inpainting
        - 0.2-0.5: severe glare, challenging to fix
        - 0.0-0.2: extreme glare everywhere, very difficult
    """
    h, w = original.shape[:2]
    total_pixels = h * w

    # Compute glare area ratio
    glare_pixels = np.sum(glare_mask > 0)
    area_ratio = glare_pixels / total_pixels

    if area_ratio == 0:
        # No glare detected, perfect
        return 1.0

    # Factor 1: Area ratio (more glare = lower confidence)
    # 0-5% glare: minimal impact
    # 5-15% glare: moderate impact
    # 15-30% glare: significant impact
    # 30%+ glare: severe impact
    if area_ratio < 0.05:
        area_score = 1.0
    elif area_ratio < 0.15:
        area_score = 0.9 - (area_ratio - 0.05) * 3.0  # Linear decay from 0.9 to 0.6
    elif area_ratio < 0.30:
        area_score = 0.6 - (area_ratio - 0.15) * 2.0  # Linear decay from 0.6 to 0.3
    else:
        area_score = max(0.1, 0.3 - (area_ratio - 0.30) * 0.5)

    # Factor 2: Spatial distribution (clustered glare vs scattered)
    # Compute glare region centrality
    # Glare near edges is easier to inpaint than glare covering central content
    glare_coords = np.argwhere(glare_mask > 0)

    if len(glare_coords) > 0:
        # Compute mean distance from image center
        center_y, center_x = h / 2, w / 2
        distances = np.sqrt(
            (glare_coords[:, 0] - center_y) ** 2 + (glare_coords[:, 1] - center_x) ** 2
        )
        mean_distance = np.mean(distances)
        max_distance = np.sqrt(center_y**2 + center_x**2)
        centrality_ratio = 1.0 - (mean_distance / max_distance)

        # Glare at edges (low centrality) is easier to fix
        # centrality_ratio: 0 (at edges) -> 1 (at center)
        # distribution_score: 1.0 (edges) -> 0.7 (center)
        distribution_score = 1.0 - centrality_ratio * 0.3
    else:
        distribution_score = 1.0

    # Factor 3: Number of glare regions
    # Fewer, larger regions are easier to handle than many scattered spots
    from cv2 import findContours, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE

    contours, _ = findContours(glare_mask, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
    num_regions = len(contours)

    if num_regions == 0:
        region_score = 1.0
    elif num_regions <= 3:
        region_score = 1.0
    elif num_regions <= 10:
        region_score = 0.9 - (num_regions - 3) * 0.05  # Decay from 0.9 to 0.55
    else:
        region_score = max(0.4, 0.55 - (num_regions - 10) * 0.02)

    # Combine factors with weighted average
    # Area is most important, then distribution, then region count
    confidence = area_score * 0.5 + distribution_score * 0.3 + region_score * 0.2

    # Clamp to [0, 1]
    confidence = np.clip(confidence, 0.0, 1.0)

    logger.debug(
        f"Glare confidence: {confidence:.3f} "
        f"(area={area_score:.3f}, dist={distribution_score:.3f}, regions={region_score:.3f})"
    )

    return float(confidence)
