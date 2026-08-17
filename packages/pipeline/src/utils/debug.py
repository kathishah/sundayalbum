"""Debug visualization and output utilities."""

import logging
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def save_debug_image(
    image: np.ndarray,
    output_path: Union[str, Path],
    description: Optional[str] = None,
    quality: int = 95
) -> None:
    """Save debug image with step numbering, always as JPEG for easy viewing.

    Args:
        image: Image array as float32 RGB [0,1] or uint8 RGB [0,255]
        output_path: Path to save debug image (should include step number prefix)
        description: Optional description to log
        quality: JPEG quality (0-100)
    """
    output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to uint8 if needed
    if image.dtype == np.float32 or image.dtype == np.float64:
        if image.max() <= 1.0:
            img_uint8 = (image * 255).astype(np.uint8)
        else:
            img_uint8 = image.astype(np.uint8)
    else:
        img_uint8 = image

    # Ensure we have the right number of channels
    if img_uint8.ndim == 2:
        # Grayscale - convert to BGR for OpenCV
        img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_GRAY2BGR)
    elif img_uint8.shape[2] == 3:
        # RGB - convert to BGR for OpenCV
        img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR)
    elif img_uint8.shape[2] == 4:
        # RGBA - convert to BGR
        img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGBA2BGR)
    else:
        raise ValueError(f"Unsupported number of channels: {img_uint8.shape[2]}")

    # Always save as JPEG (not HEIC/DNG) for easy viewing
    # Force .jpg extension
    if output_path.suffix.lower() not in ['.jpg', '.jpeg']:
        output_path = output_path.with_suffix('.jpg')

    # Save with OpenCV
    cv2.imwrite(
        str(output_path),
        img_bgr,
        [cv2.IMWRITE_JPEG_QUALITY, quality]
    )

    if description:
        logger.debug(f"Saved debug image: {output_path} - {description}")
    else:
        logger.debug(f"Saved debug image: {output_path}")


def save_debug_text(
    text: str,
    output_path: Union[str, Path],
    description: Optional[str] = None
) -> None:
    """Save debug text output.

    Args:
        text: Text content to save
        output_path: Path to save text file
        description: Optional description to log
    """
    output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write text file
    output_path.write_text(text)

    if description:
        logger.debug(f"Saved debug text: {output_path} - {description}")
    else:
        logger.debug(f"Saved debug text: {output_path}")


def draw_photo_detections(
    image: np.ndarray,
    detections: list,
    line_thickness: int = 3
) -> np.ndarray:
    """Draw photo detection bounding boxes and labels on image.

    Args:
        image: Image array as float32 RGB [0,1]
        detections: List of PhotoDetection objects
        line_thickness: Thickness of bounding box lines

    Returns:
        Image with detections drawn as float32 RGB [0,1]
    """
    # Make a copy and convert to uint8 for OpenCV drawing
    if image.max() <= 1.0:
        img_viz = (image * 255).astype(np.uint8)
    else:
        img_viz = image.astype(np.uint8)

    # Convert RGB to BGR for OpenCV
    img_viz = cv2.cvtColor(img_viz, cv2.COLOR_RGB2BGR)

    # Draw each detection
    for i, det in enumerate(detections, 1):
        # Get bounding box coordinates
        x1, y1, x2, y2 = det.bbox

        # Choose color based on region type (if available)
        region_type = getattr(det, 'region_type', 'photo')
        if region_type == "photo":
            color = (0, 255, 0)  # Green for photos
        elif region_type == "caption":
            color = (255, 128, 0)  # Orange for captions
        elif region_type == "decoration":
            color = (128, 128, 128)  # Gray for decorations
        else:
            color = (0, 0, 255)  # Red for unknown

        # Draw rectangle
        cv2.rectangle(img_viz, (x1, y1), (x2, y2), color, line_thickness)

        # Prepare label text
        label = f"#{i} {region_type}"
        if hasattr(det, 'orientation') and det.orientation != "unknown":
            label += f" ({det.orientation})"

        # Calculate text size for background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        font_thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(
            label, font, font_scale, font_thickness
        )

        # Draw label background
        label_y = max(y1 - 10, text_height + 10)
        cv2.rectangle(
            img_viz,
            (x1, label_y - text_height - baseline - 5),
            (x1 + text_width + 10, label_y + baseline),
            color,
            -1  # Filled
        )

        # Draw label text
        cv2.putText(
            img_viz,
            label,
            (x1 + 5, label_y - 5),
            font,
            font_scale,
            (255, 255, 255),  # White text
            font_thickness,
            cv2.LINE_AA
        )

        # Draw confidence score
        conf_label = f"conf: {det.confidence:.2f}"
        cv2.putText(
            img_viz,
            conf_label,
            (x1 + 5, y2 - 10),
            font,
            0.5,
            color,
            1,
            cv2.LINE_AA
        )

    # Convert back to RGB and float32
    img_viz = cv2.cvtColor(img_viz, cv2.COLOR_BGR2RGB)
    return img_viz.astype(np.float32) / 255.0


def create_comparison_image(
    images: list[np.ndarray],
    titles: Optional[list[str]] = None,
    max_width: int = 1920
) -> np.ndarray:
    """Create side-by-side comparison of multiple images.

    Args:
        images: List of images as float32 RGB [0,1] or uint8 RGB [0,255]
        titles: Optional list of titles for each image
        max_width: Maximum width for the combined image

    Returns:
        Combined comparison image as uint8 RGB
    """
    if not images:
        raise ValueError("No images provided")

    # Convert all images to uint8 RGB
    processed_images = []
    for img in images:
        if img.dtype == np.float32 or img.dtype == np.float64:
            if img.max() <= 1.0:
                img_uint8 = (img * 255).astype(np.uint8)
            else:
                img_uint8 = img.astype(np.uint8)
        else:
            img_uint8 = img

        # Ensure RGB
        if img_uint8.ndim == 2:
            img_uint8 = cv2.cvtColor(img_uint8, cv2.COLOR_GRAY2RGB)
        elif img_uint8.shape[2] == 4:
            img_uint8 = cv2.cvtColor(img_uint8, cv2.COLOR_RGBA2RGB)

        processed_images.append(img_uint8)

    # Find the maximum height to make all images the same height
    max_height = max(img.shape[0] for img in processed_images)

    # Resize all images to the same height, preserving aspect ratio
    resized_images = []
    for img in processed_images:
        if img.shape[0] != max_height:
            scale = max_height / img.shape[0]
            new_width = int(img.shape[1] * scale)
            resized = cv2.resize(img, (new_width, max_height), interpolation=cv2.INTER_AREA)
        else:
            resized = img
        resized_images.append(resized)

    # Concatenate horizontally
    combined = np.hstack(resized_images)

    # Scale down if too wide
    if combined.shape[1] > max_width:
        scale = max_width / combined.shape[1]
        new_height = int(combined.shape[0] * scale)
        combined = cv2.resize(combined, (max_width, new_height), interpolation=cv2.INTER_AREA)

    return combined
