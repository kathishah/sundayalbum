"""Dewarping — correct barrel distortion from bowed photo surfaces.

This module detects and corrects curvature/bulging in photos, which can occur
when glossy prints bow behind plastic sleeves or from aging.
"""

import logging
from typing import Tuple, Optional

import cv2
import numpy as np
from scipy import interpolate

logger = logging.getLogger(__name__)


def correct_warp(
    photo: np.ndarray,
    detection_threshold: float = 0.02,
) -> Tuple[np.ndarray, bool]:
    """Detect and correct warping/bulging in a photo.

    This function detects barrel distortion by finding lines that should be
    straight but are curved, then applies inverse distortion to correct it.

    Args:
        photo: Photo image, float32 RGB [0, 1]
        detection_threshold: Minimum curvature ratio to trigger correction (0-1)
                            Lower = more sensitive. Default 0.02 (2% curvature)

    Returns:
        Tuple of (corrected_photo, warp_detected)
        - corrected_photo: Dewarped image, float32 RGB [0, 1]
        - warp_detected: True if significant warp was detected and corrected
    """
    h, w = photo.shape[:2]

    # Detect curvature in the image
    curvature_score, distortion_params = _detect_curvature(photo)

    logger.debug(f"Detected curvature score: {curvature_score:.4f}")

    # Only correct if curvature exceeds threshold
    if curvature_score < detection_threshold:
        logger.debug("No significant warp detected, skipping correction")
        return photo, False

    # Apply inverse distortion correction
    corrected = _apply_dewarp(photo, distortion_params)

    logger.info(f"Applied dewarp correction (curvature: {curvature_score:.4f})")

    return corrected, True


def _detect_curvature(photo: np.ndarray) -> Tuple[float, dict]:
    """Detect curvature/barrel distortion in the photo.

    Analyzes edges that should be straight (photo borders, straight lines in
    content) and measures their deviation from straightness.

    Args:
        photo: Photo image, float32 RGB [0, 1]

    Returns:
        Tuple of (curvature_score, distortion_params)
        - curvature_score: 0-1 score indicating severity (0=none, 1=severe)
        - distortion_params: Dict with distortion parameters for correction
    """
    h, w = photo.shape[:2]

    # Convert to grayscale
    gray = (photo.mean(axis=2) * 255).astype(np.uint8)

    # Edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=min(w, h) // 3,  # Long lines only
        maxLineGap=20,
    )

    if lines is None or len(lines) < 4:
        # Not enough lines to analyze
        return 0.0, {'k1': 0.0, 'k2': 0.0}

    # Analyze curvature for each detected line
    curvatures = []

    for line in lines:
        x1, y1, x2, y2 = line[0]

        # Extract points along this line from the edge image
        line_points = _extract_line_points(edges, x1, y1, x2, y2)

        if len(line_points) < 10:
            continue

        # Measure deviation from straight line
        curvature = _measure_line_curvature(line_points)
        curvatures.append(curvature)

    if not curvatures:
        return 0.0, {'k1': 0.0, 'k2': 0.0}

    # Use median curvature (robust to outliers)
    median_curvature = np.median(curvatures)

    # Estimate distortion parameters from curvature
    # k1 is the radial distortion coefficient (barrel distortion if positive)
    # This is a simplified model; full calibration would be more complex
    k1 = median_curvature * 0.5  # Empirical scaling factor
    k2 = 0.0  # Second-order distortion (rarely needed)

    distortion_params = {
        'k1': k1,
        'k2': k2,
        'center_x': w / 2,
        'center_y': h / 2,
    }

    return median_curvature, distortion_params


def _extract_line_points(
    edges: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    margin: int = 5,
) -> np.ndarray:
    """Extract edge points near a line segment.

    Args:
        edges: Edge image (binary)
        x1, y1, x2, y2: Line segment endpoints
        margin: Pixel margin around line to search

    Returns:
        Nx2 array of (x, y) points
    """
    # Create a mask for the region around the line
    h, w = edges.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    # Draw thick line on mask
    cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=margin * 2)

    # Find edge points within this region
    edge_points = np.column_stack(np.where(edges & mask))

    # edge_points are in (y, x) format, convert to (x, y)
    if len(edge_points) > 0:
        edge_points = edge_points[:, [1, 0]]

    return edge_points


def _measure_line_curvature(points: np.ndarray) -> float:
    """Measure how much a set of points deviates from a straight line.

    Args:
        points: Nx2 array of (x, y) points

    Returns:
        Curvature score (0 = perfectly straight, higher = more curved)
    """
    if len(points) < 3:
        return 0.0

    # Fit a straight line using least squares
    x = points[:, 0]
    y = points[:, 1]

    # Handle vertical lines
    if x.max() - x.min() < 1:
        # Vertical line - measure horizontal deviation
        mean_x = x.mean()
        deviations = np.abs(x - mean_x)
    else:
        # Fit line: y = mx + b
        A = np.vstack([x, np.ones(len(x))]).T
        m, b = np.linalg.lstsq(A, y, rcond=None)[0]

        # Compute perpendicular distance from each point to the line
        # Line: mx - y + b = 0
        # Distance: |mx - y + b| / sqrt(m^2 + 1)
        deviations = np.abs(m * x - y + b) / np.sqrt(m**2 + 1)

    # Curvature metric: RMS deviation normalized by line length
    line_length = np.linalg.norm(points[-1] - points[0])
    if line_length < 1:
        return 0.0

    rms_deviation = np.sqrt(np.mean(deviations**2))
    curvature = rms_deviation / line_length

    return curvature


def _apply_dewarp(photo: np.ndarray, distortion_params: dict) -> np.ndarray:
    """Apply inverse distortion to correct warping.

    Uses a lens distortion model to undistort the image.

    Args:
        photo: Photo image, float32 RGB [0, 1]
        distortion_params: Dict with 'k1', 'k2', 'center_x', 'center_y'

    Returns:
        Corrected image, float32 RGB [0, 1]
    """
    h, w = photo.shape[:2]

    k1 = distortion_params['k1']
    k2 = distortion_params.get('k2', 0.0)
    cx = distortion_params['center_x']
    cy = distortion_params['center_y']

    # Create camera matrix (simplified, assuming no other intrinsics)
    # Focal length estimated as image width (common approximation)
    fx = fy = w
    camera_matrix = np.array([
        [fx, 0, cx],
        [0, fy, cy],
        [0, 0, 1]
    ], dtype=np.float32)

    # Distortion coefficients: [k1, k2, p1, p2, k3]
    # We only use radial distortion (k1, k2), no tangential (p1, p2)
    dist_coeffs = np.array([k1, k2, 0, 0, 0], dtype=np.float32)

    # Convert to uint8 for cv2.undistort
    photo_uint8 = (photo * 255).astype(np.uint8)

    # Undistort
    try:
        undistorted_uint8 = cv2.undistort(photo_uint8, camera_matrix, dist_coeffs)

        # Convert back to float32
        undistorted = undistorted_uint8.astype(np.float32) / 255.0

        return undistorted

    except cv2.error as e:
        logger.warning(f"Failed to apply dewarp: {e}")
        return photo


def estimate_distortion_from_grid(
    photo: np.ndarray,
    grid_points: Optional[np.ndarray] = None,
) -> dict:
    """Estimate distortion parameters from a grid pattern (advanced).

    This function can be used when the photo contains a grid pattern
    (e.g., checkered background, tiled floor) to more accurately estimate
    distortion parameters.

    Args:
        photo: Photo image, float32 RGB [0, 1]
        grid_points: Optional Nx2 array of detected grid intersection points
                     If None, will attempt auto-detection

    Returns:
        Dict with distortion parameters
    """
    # This is a placeholder for more advanced distortion estimation
    # Would require:
    # 1. Detect grid intersections (Harris corners or checkerboard detection)
    # 2. Match to ideal grid pattern
    # 3. Compute distortion parameters that minimize reprojection error
    # 4. Use cv2.calibrateCamera or similar

    # For now, return default (no distortion)
    logger.debug("Grid-based distortion estimation not yet implemented")

    h, w = photo.shape[:2]
    return {
        'k1': 0.0,
        'k2': 0.0,
        'center_x': w / 2,
        'center_y': h / 2,
    }
