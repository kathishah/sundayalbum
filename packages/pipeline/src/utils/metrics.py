"""Image quality metrics for assessment and validation."""

import logging
from typing import Dict

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def compute_sharpness(image: np.ndarray) -> float:
    """Compute sharpness using Laplacian variance.

    Higher values indicate sharper images (more high-frequency detail).

    Args:
        image: RGB image, float32 [0, 1] or uint8 [0, 255]

    Returns:
        Sharpness score (typically 0-500, higher is sharper)
    """
    # Convert to grayscale for sharpness measurement
    if image.ndim == 3:
        # Convert to uint8 if needed
        if image.dtype == np.float32 or image.dtype == np.float64:
            gray = (image * 255).astype(np.uint8)
        else:
            gray = image

        # Convert to grayscale
        if gray.shape[2] == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_RGB2GRAY)
        else:
            gray = gray[:, :, 0]
    else:
        gray = image

    # Compute Laplacian (edge detection)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)

    # Variance of Laplacian = sharpness measure
    # High variance = lots of edges = sharp image
    # Low variance = few edges = blurry image
    variance = float(laplacian.var())

    return variance


def compute_histogram_stats(image: np.ndarray) -> Dict[str, float]:
    """Compute histogram-based statistics.

    Args:
        image: RGB image, float32 [0, 1]

    Returns:
        Dictionary with histogram statistics:
        - mean_brightness: Mean of all pixels [0, 1]
        - contrast: Standard deviation [0, 1]
        - dynamic_range: Max - min value [0, 1]
        - histogram_entropy: Shannon entropy of histogram
    """
    # Flatten to 1D
    pixels = image.reshape(-1, image.shape[-1]) if image.ndim == 3 else image.flatten()

    # Convert to grayscale for some metrics
    if image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(
            (image * 255).astype(np.uint8),
            cv2.COLOR_RGB2GRAY
        ) / 255.0
    else:
        gray = image

    # Mean brightness
    mean_brightness = float(np.mean(gray))

    # Contrast (standard deviation)
    contrast = float(np.std(gray))

    # Dynamic range
    dynamic_range = float(np.max(gray) - np.min(gray))

    # Histogram entropy (measure of information content)
    # Higher entropy = more varied tones
    hist, _ = np.histogram(gray, bins=256, range=(0, 1))
    hist = hist / hist.sum()  # Normalize to probabilities
    hist = hist[hist > 0]  # Remove zero bins
    entropy = float(-np.sum(hist * np.log2(hist)))

    return {
        'mean_brightness': mean_brightness,
        'contrast': contrast,
        'dynamic_range': dynamic_range,
        'histogram_entropy': entropy,
    }


def compute_noise_level(image: np.ndarray) -> float:
    """Estimate noise level using high-frequency component analysis.

    Args:
        image: RGB image, float32 [0, 1]

    Returns:
        Estimated noise level (standard deviation of noise)
    """
    # Convert to grayscale
    if image.ndim == 3:
        gray = cv2.cvtColor(
            (image * 255).astype(np.uint8),
            cv2.COLOR_RGB2GRAY
        ).astype(np.float32) / 255.0
    else:
        gray = image.astype(np.float32)

    # Apply median filter to get smoothed version
    # Median filter preserves edges while removing noise
    smoothed = cv2.medianBlur((gray * 255).astype(np.uint8), 5).astype(np.float32) / 255.0

    # Noise = difference between original and smoothed
    noise = gray - smoothed

    # Estimate noise level (robust estimation using median absolute deviation)
    mad = float(np.median(np.abs(noise - np.median(noise))))
    # Scale MAD to standard deviation estimate (for Gaussian noise)
    noise_level = mad * 1.4826

    return noise_level


def compute_blur_score(image: np.ndarray) -> float:
    """Compute blur score using frequency domain analysis.

    Lower values indicate more blur.

    Args:
        image: RGB image, float32 [0, 1]

    Returns:
        Blur score (typically 0-1, higher means sharper)
    """
    # Convert to grayscale
    if image.ndim == 3:
        gray = cv2.cvtColor(
            (image * 255).astype(np.uint8),
            cv2.COLOR_RGB2GRAY
        ).astype(np.float32)
    else:
        gray = (image * 255).astype(np.float32)

    # Compute FFT
    fft = np.fft.fft2(gray)
    fft_shift = np.fft.fftshift(fft)

    # Compute power spectrum
    magnitude = np.abs(fft_shift)

    # High frequencies are in the outer regions
    # Blur reduces high frequencies
    h, w = magnitude.shape
    center_y, center_x = h // 2, w // 2

    # Create mask for high-frequency region (outer 30%)
    y, x = np.ogrid[:h, :w]
    mask = np.sqrt((x - center_x)**2 + (y - center_y)**2) > min(h, w) * 0.35

    # Measure high-frequency power
    high_freq_power = float(np.mean(magnitude[mask]))

    # Normalize by total power
    total_power = float(np.mean(magnitude))

    if total_power > 0:
        blur_score = high_freq_power / total_power
    else:
        blur_score = 0.0

    return blur_score


def compute_color_distribution(image: np.ndarray) -> Dict[str, float]:
    """Compute color distribution statistics.

    Args:
        image: RGB image, float32 [0, 1]

    Returns:
        Dictionary with color statistics:
        - mean_r, mean_g, mean_b: Mean values per channel
        - std_r, std_g, std_b: Standard deviations per channel
        - color_balance: Ratio of channel variances (1.0 = balanced)
        - saturation_mean: Mean saturation in HSV
    """
    # Per-channel statistics
    mean_r, mean_g, mean_b = [float(np.mean(image[:, :, i])) for i in range(3)]
    std_r, std_g, std_b = [float(np.std(image[:, :, i])) for i in range(3)]

    # Color balance (how similar are the channel variances?)
    variances = [std_r**2, std_g**2, std_b**2]
    color_balance = float(min(variances) / (max(variances) + 1e-6))

    # Saturation in HSV
    hsv = cv2.cvtColor(
        (image * 255).astype(np.uint8),
        cv2.COLOR_RGB2HSV
    )
    saturation_mean = float(np.mean(hsv[:, :, 1]) / 255.0)

    return {
        'mean_r': mean_r,
        'mean_g': mean_g,
        'mean_b': mean_b,
        'std_r': std_r,
        'std_g': std_g,
        'std_b': std_b,
        'color_balance': color_balance,
        'saturation_mean': saturation_mean,
    }
