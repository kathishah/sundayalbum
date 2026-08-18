"""Combined quality assessment using programmatic metrics and optional AI."""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.ai.claude_vision import assess_quality, QualityAssessment
from src.utils.metrics import compute_sharpness, compute_histogram_stats


def _compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """Compute structural similarity index (SSIM) between two float32 RGB images.

    Pure numpy/scipy implementation — no scikit-image dependency.

    Args:
        img1: First image, float32 RGB [0, 1], shape (H, W, 3).
        img2: Second image, float32 RGB [0, 1], shape (H, W, 3).

    Returns:
        Mean SSIM across all three channels, in [-1, 1].
    """
    from scipy.ndimage import gaussian_filter  # scipy is already a project dependency

    C1 = (0.01) ** 2   # stability constant for luminance
    C2 = (0.03) ** 2   # stability constant for contrast

    scores = []
    for c in range(img1.shape[2]):
        x = img1[:, :, c].astype(np.float64)
        y = img2[:, :, c].astype(np.float64)

        mu_x = gaussian_filter(x, sigma=1.5)
        mu_y = gaussian_filter(y, sigma=1.5)

        mu_x2 = mu_x * mu_x
        mu_y2 = mu_y * mu_y
        mu_xy = mu_x * mu_y

        sig_x2 = gaussian_filter(x * x, sigma=1.5) - mu_x2
        sig_y2 = gaussian_filter(y * y, sigma=1.5) - mu_y2
        sig_xy = gaussian_filter(x * y, sigma=1.5) - mu_xy

        ssim_map = (
            (2.0 * mu_xy + C1) * (2.0 * sig_xy + C2)
        ) / (
            (mu_x2 + mu_y2 + C1) * (sig_x2 + sig_y2 + C2)
        )
        scores.append(float(np.mean(ssim_map)))

    return float(np.mean(scores))

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Programmatic quality metrics."""

    ssim_score: float  # Structural similarity (0-1, higher is more similar)
    sharpness_original: float  # Laplacian variance
    sharpness_processed: float
    sharpness_improvement: float  # Ratio (processed / original)
    contrast_original: float  # Standard deviation of pixel values
    contrast_processed: float
    contrast_improvement: float  # Ratio
    saturation_original: float  # Mean saturation in HSV
    saturation_processed: float
    color_shift: float  # Mean absolute difference in color channels
    brightness_change: float  # Mean absolute difference in brightness


@dataclass
class QualityReport:
    """Combined quality assessment report."""

    # Programmatic metrics
    metrics: QualityMetrics

    # Optional AI assessment
    ai_assessment: Optional[QualityAssessment]

    # Overall quality score (combines metrics + AI if available)
    overall_quality_score: float  # 0-100 scale

    # Processing metadata
    notes: list[str]


def compute_quality_metrics(
    original: np.ndarray,
    processed: np.ndarray
) -> QualityMetrics:
    """Compute programmatic quality metrics.

    Args:
        original: Original image, RGB float32 [0, 1]
        processed: Processed image, RGB float32 [0, 1]

    Returns:
        QualityMetrics object
    """
    import cv2

    # Ensure images are same size (SSIM requires it)
    if original.shape != processed.shape:
        logger.warning(
            f"Image size mismatch: original {original.shape}, processed {processed.shape}. "
            f"Resizing processed to match original for comparison."
        )
        processed = cv2.resize(
            processed,
            (original.shape[1], original.shape[0]),
            interpolation=cv2.INTER_AREA
        )

    # 1. SSIM (Structural Similarity Index)
    # Higher = more similar (0-1 scale)
    # For restoration, we expect SSIM to be moderate (0.7-0.9)
    # Too high (>0.95) means nothing changed, too low (<0.5) means over-processing
    ssim_score = _compute_ssim(original, processed)

    # 2. Sharpness (Laplacian variance)
    # Higher = sharper
    sharpness_orig = compute_sharpness(original)
    sharpness_proc = compute_sharpness(processed)
    sharpness_improvement = sharpness_proc / max(sharpness_orig, 1e-6)

    # 3. Contrast (standard deviation)
    # Higher = more contrast
    contrast_orig = float(np.std(original))
    contrast_proc = float(np.std(processed))
    contrast_improvement = contrast_proc / max(contrast_orig, 1e-6)

    # 4. Saturation (mean saturation in HSV)
    # Convert to HSV and extract S channel
    original_hsv = cv2.cvtColor(
        (original * 255).astype(np.uint8),
        cv2.COLOR_RGB2HSV
    )
    processed_hsv = cv2.cvtColor(
        (processed * 255).astype(np.uint8),
        cv2.COLOR_RGB2HSV
    )

    saturation_orig = float(np.mean(original_hsv[:, :, 1]) / 255.0)
    saturation_proc = float(np.mean(processed_hsv[:, :, 1]) / 255.0)

    # 5. Color shift (mean absolute difference across RGB channels)
    color_diff = np.abs(original - processed)
    color_shift = float(np.mean(color_diff))

    # 6. Brightness change (mean absolute difference in value)
    brightness_diff = np.abs(
        original_hsv[:, :, 2].astype(float) - processed_hsv[:, :, 2].astype(float)
    )
    brightness_change = float(np.mean(brightness_diff) / 255.0)

    return QualityMetrics(
        ssim_score=float(ssim_score),
        sharpness_original=float(sharpness_orig),
        sharpness_processed=float(sharpness_proc),
        sharpness_improvement=float(sharpness_improvement),
        contrast_original=float(contrast_orig),
        contrast_processed=float(contrast_proc),
        contrast_improvement=float(contrast_improvement),
        saturation_original=float(saturation_orig),
        saturation_processed=float(saturation_proc),
        color_shift=float(color_shift),
        brightness_change=float(brightness_change),
    )


def compute_overall_quality_score(
    metrics: QualityMetrics,
    ai_assessment: Optional[QualityAssessment] = None
) -> float:
    """Compute overall quality score from metrics and optional AI assessment.

    Args:
        metrics: Programmatic quality metrics
        ai_assessment: Optional AI assessment

    Returns:
        Overall quality score (0-100 scale)
    """
    # Programmatic scoring (0-100 scale)
    score = 0.0
    notes = []

    # 1. SSIM (25 points): 0.7-0.95 is good range
    # Too low = over-processing, too high = no change
    if metrics.ssim_score < 0.5:
        ssim_points = 0.0
        notes.append("SSIM very low (over-processing)")
    elif metrics.ssim_score > 0.95:
        ssim_points = 10.0
        notes.append("SSIM very high (minimal change)")
    else:
        # Optimal range: 0.75-0.90
        if 0.75 <= metrics.ssim_score <= 0.90:
            ssim_points = 25.0
        elif 0.70 <= metrics.ssim_score < 0.75:
            ssim_points = 20.0 + (metrics.ssim_score - 0.70) * 100
        elif 0.90 < metrics.ssim_score <= 0.95:
            ssim_points = 20.0 + (0.95 - metrics.ssim_score) * 100
        else:
            ssim_points = 15.0

    score += ssim_points

    # 2. Sharpness improvement (25 points): 1.0-1.3x is good
    if metrics.sharpness_improvement < 0.95:
        sharp_points = 0.0
        notes.append("Sharpness decreased")
    elif metrics.sharpness_improvement > 1.5:
        sharp_points = 10.0
        notes.append("Over-sharpened")
    else:
        # Optimal range: 1.05-1.25
        if 1.05 <= metrics.sharpness_improvement <= 1.25:
            sharp_points = 25.0
        elif 1.0 <= metrics.sharpness_improvement < 1.05:
            sharp_points = 15.0 + (metrics.sharpness_improvement - 1.0) * 200
        elif 1.25 < metrics.sharpness_improvement <= 1.5:
            sharp_points = 15.0 + (1.5 - metrics.sharpness_improvement) * 40
        else:
            sharp_points = 10.0

    score += sharp_points

    # 3. Contrast improvement (25 points): 1.0-1.5x is good
    if metrics.contrast_improvement < 0.95:
        contrast_points = 0.0
        notes.append("Contrast decreased")
    elif metrics.contrast_improvement > 2.0:
        contrast_points = 10.0
        notes.append("Over-enhanced contrast")
    else:
        # Optimal range: 1.1-1.5
        if 1.1 <= metrics.contrast_improvement <= 1.5:
            contrast_points = 25.0
        elif 1.0 <= metrics.contrast_improvement < 1.1:
            contrast_points = 15.0 + (metrics.contrast_improvement - 1.0) * 100
        elif 1.5 < metrics.contrast_improvement <= 2.0:
            contrast_points = 15.0 + (2.0 - metrics.contrast_improvement) * 20
        else:
            contrast_points = 10.0

    score += contrast_points

    # 4. Color shift (25 points): lower is better, but some change is expected
    # Typical good range: 0.01-0.05 (1-5% change)
    if metrics.color_shift > 0.15:
        color_points = 0.0
        notes.append("Excessive color shift")
    elif metrics.color_shift < 0.005:
        color_points = 10.0
        notes.append("Minimal color correction")
    else:
        # Optimal range: 0.01-0.05
        if 0.01 <= metrics.color_shift <= 0.05:
            color_points = 25.0
        elif 0.005 <= metrics.color_shift < 0.01:
            color_points = 20.0 + (metrics.color_shift - 0.005) * 1000
        elif 0.05 < metrics.color_shift <= 0.15:
            color_points = 10.0 + (0.15 - metrics.color_shift) * 100
        else:
            color_points = 5.0

    score += color_points

    # If AI assessment available, blend scores (70% programmatic, 30% AI)
    if ai_assessment and ai_assessment.confidence > 0.5:
        ai_score = ai_assessment.overall_score * 10.0  # Scale to 0-100
        score = score * 0.7 + ai_score * 0.3
        notes.append(f"AI assessment included (confidence={ai_assessment.confidence:.2f})")

    return float(np.clip(score, 0.0, 100.0))


def assess_quality_full(
    original: np.ndarray,
    processed: np.ndarray,
    use_ai: bool = False,
    api_key: Optional[str] = None
) -> QualityReport:
    """Full quality assessment with metrics and optional AI.

    Args:
        original: Original image, RGB float32 [0, 1]
        processed: Processed image, RGB float32 [0, 1]
        use_ai: Whether to use AI assessment (requires API key)
        api_key: Anthropic API key (if use_ai=True)

    Returns:
        QualityReport with all metrics and overall score
    """
    notes = []

    # 1. Compute programmatic metrics
    logger.debug("Computing programmatic quality metrics")
    metrics = compute_quality_metrics(original, processed)

    # 2. Optional AI assessment
    ai_assessment = None
    if use_ai:
        try:
            logger.debug("Running AI quality assessment")
            ai_assessment = assess_quality(original, processed, api_key)
            notes.append("AI quality assessment completed")
        except Exception as e:
            logger.warning(f"AI quality assessment failed: {e}")
            notes.append(f"AI assessment skipped: {e}")

    # 3. Compute overall score
    overall_score = compute_overall_quality_score(metrics, ai_assessment)

    # Add metric-based notes
    if metrics.ssim_score < 0.7:
        notes.append("Low SSIM - significant changes made")
    if metrics.sharpness_improvement > 1.3:
        notes.append("High sharpness improvement")
    if metrics.contrast_improvement > 1.5:
        notes.append("High contrast improvement")
    if metrics.color_shift > 0.1:
        notes.append("Significant color correction applied")

    return QualityReport(
        metrics=metrics,
        ai_assessment=ai_assessment,
        overall_quality_score=overall_score,
        notes=notes
    )
