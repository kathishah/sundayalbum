"""Detect album page boundaries in images.

Uses GrabCut iterative foreground/background segmentation to find the boundary
of a print or album page against its background.

GrabCut is initialised with a rectangle inset 2% from the image edges and runs
on a downsampled copy (longest side capped at 800 px) for speed, then scales
the resulting corner coordinates back to the original resolution.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Maximum area ratio accepted from the mask-based detection.
# If the foreground fills essentially the whole frame there was nothing to crop.
_MAX_AREA_RATIO = 0.99


@dataclass
class PageDetection:
    """Result of page boundary detection."""

    corners: np.ndarray  # shape (4, 2) — four corner points as (x, y)
    confidence: float    # 0.0 to 1.0
    is_full_frame: bool  # True if no clear boundary found, using full image
    area_ratio: float = field(default=0.0)  # Detected quad area / total image area
    photo_quads: Optional[List[np.ndarray]] = field(default=None)
    # When GrabCut finds 2+ separate foreground blobs (e.g. two prints on a dark
    # background), this list holds one (4, 2) corner array per blob — in the
    # same coordinate space as ``corners``.  The pipeline uses these to extract
    # each photo directly from the pre-warp image, bypassing the normal photo-
    # detection step which fails on merged-hull spreads.


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order four corner points as: top-left, top-right, bottom-right, bottom-left.

    Args:
        pts: Array of shape (4, 2) with (x, y) coordinates.

    Returns:
        Ordered array of shape (4, 2).
    """
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()

    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]   # top-left
    ordered[1] = pts[np.argmin(d)]   # top-right
    ordered[2] = pts[np.argmax(s)]   # bottom-right
    ordered[3] = pts[np.argmax(d)]   # bottom-left

    return ordered


def _mask_to_quad(
    mask: np.ndarray,
    image_h: int,
    image_w: int,
    image_area: float,
    min_area_ratio: float,
    max_area_ratio: float = _MAX_AREA_RATIO,
) -> Tuple[Optional[np.ndarray], Optional[List[np.ndarray]]]:
    """Convert a binary foreground mask to a quadrilateral boundary.

    Cleans the mask with morphological ops, finds significant foreground
    regions, and returns:
      - the minimum-area bounding rectangle of their convex hull as 4 corners
        (the overall page boundary), and
      - a list of individual blob corners when 2+ significant regions are found
        (used by the pipeline to extract each photo independently).

    Args:
        mask: Binary mask (uint8, 0 or 255) — 255 is foreground.
        image_h: Image height in pixels.
        image_w: Image width in pixels.
        image_area: Total image area (h * w).
        min_area_ratio: Minimum foreground area as fraction of image area.
        max_area_ratio: Maximum foreground area as fraction of image area.

    Returns:
        Tuple of:
          - Ordered corner points (4, 2) float32, or None if not found.
          - List of per-blob corner arrays (each (4, 2) float32), or None if
            only one significant blob exists.
    """
    # Morphological close to fill holes (e.g., glare patches inside the subject),
    # then open to remove small noise. Kernel proportional to image size.
    kernel_size = max(15, int(min(image_h, image_w) * 0.015))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None

    # Collect all significant foreground contours, not just the largest one.
    # This handles open album spreads where GrabCut produces separate blobs for
    # each page (e.g. two photos on facing pages): taking only the largest blob
    # would crop out the second page entirely.  Any contour that is at least
    # 25% of min_area_ratio in size is considered significant (generous enough
    # to capture real photo regions while rejecting dust/noise specks).
    component_min = image_area * max(0.01, min_area_ratio * 0.25)
    significant = [c for c in contours if cv2.contourArea(c) >= component_min]

    if not significant:
        return None, None

    # Combined area check — the union of all significant regions must still
    # fall within [min_area_ratio, max_area_ratio].
    area_ratio = sum(cv2.contourArea(c) for c in significant) / image_area

    if area_ratio < min_area_ratio or area_ratio > max_area_ratio:
        logger.debug(
            f"Mask-to-quad: rejected contour (area_ratio={area_ratio:.3f}, "
            f"bounds=[{min_area_ratio:.2f}, {max_area_ratio:.2f}])"
        )
        return None, None

    logger.debug(
        f"Mask-to-quad: {len(significant)} significant component(s), "
        f"combined area_ratio={area_ratio:.3f}"
    )

    # When 2+ blobs exist, compute individual per-blob quads so the pipeline
    # can extract each photo independently (bypassing photo detection on the
    # merged hull image, which fails when there is no white paper gap).
    individual_quads: Optional[List[np.ndarray]] = None
    if len(significant) >= 2:
        individual_quads = []
        for contour in significant:
            b_hull = cv2.convexHull(contour)
            b_rect = cv2.minAreaRect(b_hull)
            b_box = cv2.boxPoints(b_rect)
            b_corners = np.array(b_box, dtype=np.float32)
            b_corners[:, 0] = np.clip(b_corners[:, 0], 0, image_w - 1)
            b_corners[:, 1] = np.clip(b_corners[:, 1], 0, image_h - 1)
            individual_quads.append(_order_corners(b_corners))

    # Build convex hull over all significant foreground points so that the
    # resulting quad encloses every detected region (handles multi-blob spreads).
    all_points = np.vstack(significant)
    hull = cv2.convexHull(all_points)
    rect = cv2.minAreaRect(hull)
    box = cv2.boxPoints(rect)
    corners = np.array(box, dtype=np.float32)

    corners[:, 0] = np.clip(corners[:, 0], 0, image_w - 1)
    corners[:, 1] = np.clip(corners[:, 1], 0, image_h - 1)

    return _order_corners(corners), individual_quads


def detect_page(
    image: np.ndarray,
    min_area_ratio: float = 0.3,
    grabcut_iterations: int = 5,
    grabcut_max_dimension: int = 800,
) -> "PageDetection":
    """Detect album page or photo print boundaries using GrabCut segmentation.

    Runs GrabCut initialised with a rectangle inset 2% from the image edges.
    GrabCut iteratively refines the foreground/background classification using
    Gaussian Mixture Models, cleanly separating prints from table surfaces and
    album pages from their surroundings.

    For speed, GrabCut runs on a downsampled copy of the image (longest side
    capped at grabcut_max_dimension). Corner coordinates are scaled back to the
    original resolution after detection.

    Falls back to full-frame if GrabCut cannot find a valid boundary.

    Args:
        image: Input image as float32 RGB [0, 1], shape (H, W, 3).
        min_area_ratio: Minimum detected area as fraction of total image area.
            Regions smaller than this are ignored. Default 0.3.
        grabcut_iterations: Number of GrabCut EM iterations. Default 5.
        grabcut_max_dimension: Longest side of the working image for GrabCut.
            Larger values are more accurate but slower. Default 800.

    Returns:
        PageDetection with detected corners, confidence, area_ratio, and
        is_full_frame flag.
    """
    height, width = image.shape[:2]
    image_area = float(height * width)

    # ------------------------------------------------------------------
    # Downsample for GrabCut — coarse segmentation is all we need, and
    # time scales linearly with pixel count.
    # ------------------------------------------------------------------
    longest = max(height, width)
    if longest > grabcut_max_dimension:
        scale = grabcut_max_dimension / longest
        gc_h = max(50, int(height * scale))
        gc_w = max(50, int(width * scale))
        gc_uint8 = cv2.resize(
            (image * 255).astype(np.uint8),
            (gc_w, gc_h),
            interpolation=cv2.INTER_AREA,
        )
        scale_x = width / gc_w
        scale_y = height / gc_h
    else:
        gc_h, gc_w = height, width
        gc_uint8 = (image * 255).astype(np.uint8)
        scale_x = scale_y = 1.0

    gc_bgr = cv2.cvtColor(gc_uint8, cv2.COLOR_RGB2BGR)

    # Init rect: 2% inset from each edge. GrabCut treats everything inside
    # as "probably foreground" on the first iteration.
    margin_x = max(2, int(gc_w * 0.02))
    margin_y = max(2, int(gc_h * 0.02))
    rect = (margin_x, margin_y, gc_w - 2 * margin_x, gc_h - 2 * margin_y)

    gc_mask = np.zeros((gc_h, gc_w), dtype=np.uint8)
    bg_model = np.zeros((1, 65), dtype=np.float64)
    fg_model = np.zeros((1, 65), dtype=np.float64)

    corners: Optional[np.ndarray] = None
    photo_quads: Optional[List[np.ndarray]] = None

    try:
        cv2.grabCut(
            gc_bgr, gc_mask, rect,
            bg_model, fg_model,
            grabcut_iterations, cv2.GC_INIT_WITH_RECT,
        )

        # Definite foreground (GC_FGD) + probable foreground (GC_PR_FGD)
        fg_mask = np.where(
            (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
            np.uint8(255),
            np.uint8(0),
        )

        fg_ratio = np.count_nonzero(fg_mask) / (gc_h * gc_w)
        logger.debug(
            f"GrabCut: foreground coverage={fg_ratio:.3f} "
            f"(ran on {gc_w}×{gc_h})"
        )

        corners_small, individual_quads_small = _mask_to_quad(
            fg_mask, gc_h, gc_w, float(gc_h * gc_w), min_area_ratio,
        )
        if corners_small is not None:
            corners = corners_small.copy()
            corners[:, 0] = np.clip(corners[:, 0] * scale_x, 0, width - 1)
            corners[:, 1] = np.clip(corners[:, 1] * scale_y, 0, height - 1)

            if individual_quads_small is not None:
                photo_quads = []
                for q in individual_quads_small:
                    q_scaled = q.copy()
                    q_scaled[:, 0] = np.clip(q_scaled[:, 0] * scale_x, 0, width - 1)
                    q_scaled[:, 1] = np.clip(q_scaled[:, 1] * scale_y, 0, height - 1)
                    photo_quads.append(q_scaled)
                logger.info(
                    f"Multi-blob page: {len(photo_quads)} separate foreground regions detected"
                )

    except cv2.error as e:
        logger.warning(f"GrabCut failed: {e}")

    # ------------------------------------------------------------------
    # Full-frame fallback
    # ------------------------------------------------------------------
    if corners is None:
        full_corners = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ], dtype=np.float32)
        logger.info("GrabCut found no boundary, using full frame")
        return PageDetection(
            corners=full_corners,
            confidence=0.0,
            is_full_frame=True,
            area_ratio=1.0,
        )

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------
    quad_area = cv2.contourArea(corners.astype(np.int32))
    area_ratio = quad_area / image_area

    _, (br_w, br_h), _ = cv2.minAreaRect(corners.astype(np.int32))
    rectangularity = quad_area / max(br_w * br_h, 1.0)
    confidence = min(1.0, area_ratio * rectangularity * 2.0)

    logger.info(
        f"Page detected via grabcut: area_ratio={area_ratio:.3f}, "
        f"rectangularity={rectangularity:.3f}, confidence={confidence:.3f}"
    )

    return PageDetection(
        corners=corners,
        confidence=confidence,
        is_full_frame=False,
        area_ratio=area_ratio,
        photo_quads=photo_quads,
    )


def draw_page_detection(
    image: np.ndarray,
    detection: PageDetection,
) -> np.ndarray:
    """Draw page detection overlay on image for debugging.

    Args:
        image: Input image as float32 RGB [0, 1].
        detection: PageDetection result.

    Returns:
        Image with overlay as float32 RGB [0, 1].
    """
    img_uint8 = (image * 255).astype(np.uint8).copy()
    corners = detection.corners.astype(np.int32)

    for i in range(4):
        pt1 = tuple(corners[i])
        pt2 = tuple(corners[(i + 1) % 4])
        cv2.line(img_uint8, pt1, pt2, (0, 255, 0), 3)

    for corner in corners:
        cv2.circle(img_uint8, tuple(corner), 10, (255, 0, 0), -1)

    text = f"conf:{detection.confidence:.2f} area:{detection.area_ratio:.2f}"
    if detection.is_full_frame:
        text += " (full_frame)"
    cv2.putText(img_uint8, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    return img_uint8.astype(np.float32) / 255.0
