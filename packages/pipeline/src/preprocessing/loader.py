"""Image loading module with support for HEIC, DNG, JPEG, and PNG formats."""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
from PIL import Image, ExifTags

logger = logging.getLogger(__name__)


class ImageMetadata:
    """Metadata extracted from loaded image."""

    def __init__(
        self,
        original_size: Tuple[int, int],
        format: str,
        bit_depth: int,
        orientation: int = 1
    ) -> None:
        self.original_size = original_size  # (width, height)
        self.format = format
        self.bit_depth = bit_depth
        self.orientation = orientation


def _apply_exif_orientation(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation to PIL Image."""
    try:
        # Get EXIF data
        exif = img._getexif()
        if exif is None:
            return img

        # Find orientation tag
        orientation_key = None
        for tag, name in ExifTags.TAGS.items():
            if name == 'Orientation':
                orientation_key = tag
                break

        if orientation_key is None:
            return img

        orientation = exif.get(orientation_key)

        if orientation is None:
            return img

        # Apply rotation based on orientation
        if orientation == 2:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            img = img.rotate(180, expand=True)
        elif orientation == 4:
            img = img.rotate(180, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 5:
            img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            img = img.rotate(-90, expand=True)
        elif orientation == 7:
            img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            img = img.rotate(90, expand=True)

        logger.debug(f"Applied EXIF orientation: {orientation}")

    except (AttributeError, KeyError, IndexError) as e:
        logger.debug(f"Could not read EXIF orientation: {e}")

    return img


def load_heic(path: str) -> Tuple[np.ndarray, ImageMetadata]:
    """Load HEIC/HEIF image using pillow-heif.

    Args:
        path: Path to HEIC file

    Returns:
        Tuple of (RGB array as float32 [0,1], metadata)
    """
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError as e:
        raise ImportError(
            "pillow-heif is required for HEIC support. "
            "Install with: pip install pillow-heif"
        ) from e

    img = Image.open(path)
    original_size = img.size  # (width, height)

    # Apply EXIF orientation
    img = _apply_exif_orientation(img)

    # Convert to RGB array
    arr = np.array(img).astype(np.float32) / 255.0

    # Ensure RGB (handle RGBA or grayscale)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.shape[2] == 4:
        arr = arr[:, :, :3]

    metadata = ImageMetadata(
        original_size=original_size,
        format="HEIC",
        bit_depth=8
    )

    logger.info(f"Loaded HEIC: {path} ({arr.shape[1]}x{arr.shape[0]})")

    return arr, metadata


def load_dng(path: str) -> Tuple[np.ndarray, ImageMetadata]:
    """Load DNG/RAW image using rawpy.

    Args:
        path: Path to DNG file

    Returns:
        Tuple of (RGB array as float32 [0,1], metadata)
    """
    try:
        import rawpy
    except ImportError as e:
        raise ImportError(
            "rawpy is required for DNG/RAW support. "
            "Install with: pip install rawpy"
        ) from e

    with rawpy.imread(path) as raw:
        # Get original dimensions
        original_size = (raw.sizes.width, raw.sizes.height)

        # Demosaic with camera white balance, sRGB output, 16-bit
        rgb = raw.postprocess(
            use_camera_wb=True,
            output_color=rawpy.ColorSpace.sRGB,
            output_bps=16,
            no_auto_bright=False,
        )

    # Convert 16-bit to float32 [0, 1]
    arr = rgb.astype(np.float32) / 65535.0

    metadata = ImageMetadata(
        original_size=original_size,
        format="DNG",
        bit_depth=16
    )

    logger.info(f"Loaded DNG: {path} ({arr.shape[1]}x{arr.shape[0]}, 16-bit)")

    return arr, metadata


def load_standard(path: str) -> Tuple[np.ndarray, ImageMetadata]:
    """Load JPEG, PNG, or TIFF using PIL.

    Args:
        path: Path to image file

    Returns:
        Tuple of (RGB array as float32 [0,1], metadata)
    """
    img = Image.open(path)
    original_size = img.size

    # Apply EXIF orientation
    img = _apply_exif_orientation(img)

    # Convert to RGB array
    arr = np.array(img).astype(np.float32) / 255.0

    # Ensure RGB
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.shape[2] == 4:
        arr = arr[:, :, :3]

    ext = Path(path).suffix.lower()
    format_name = ext.lstrip('.').upper()

    metadata = ImageMetadata(
        original_size=original_size,
        format=format_name,
        bit_depth=8
    )

    logger.info(f"Loaded {format_name}: {path} ({arr.shape[1]}x{arr.shape[0]})")

    return arr, metadata


def load_image(path: str) -> Tuple[np.ndarray, ImageMetadata]:
    """Load image from any supported format.

    Supports HEIC, DNG, JPEG, PNG, TIFF. Returns normalized float32 RGB array [0, 1].

    Args:
        path: Path to image file

    Returns:
        Tuple of (RGB array as float32 [0,1] with shape (H, W, 3), metadata)

    Raises:
        ValueError: If file format is not supported
        FileNotFoundError: If file does not exist
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    ext = path_obj.suffix.lower()

    if ext in ('.heic', '.heif'):
        return load_heic(path)
    elif ext in ('.dng', '.cr2', '.nef', '.arw'):
        return load_dng(path)
    elif ext in ('.jpg', '.jpeg', '.png', '.tiff', '.tif'):
        return load_standard(path)
    else:
        raise ValueError(f"Unsupported image format: {ext}")
