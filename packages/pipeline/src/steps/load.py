"""Step: load — read source image, apply EXIF orientation, write debug frame."""

import logging
from typing import Optional

from src.pipeline import PipelineConfig
from src.storage.backend import StorageBackend

logger = logging.getLogger(__name__)

# Extensions to probe when searching for the uploaded source file.
_UPLOAD_EXTENSIONS = [
    ".heic", ".HEIC",
    ".jpg", ".JPG", ".jpeg", ".JPEG",
    ".png", ".PNG",
    ".dng", ".DNG",
]


def run(
    storage: StorageBackend,
    stem: str,
    config: PipelineConfig,
    photo_index: Optional[int] = None,
) -> dict:
    """Load the source image from storage and write a JPEG debug frame.

    Reads from ``uploads/{stem}.{ext}`` (probes common extensions).
    Writes ``debug/{stem}_01_loaded.jpg``.

    Args:
        storage: Active storage backend.
        stem: Input file stem (e.g. ``"IMG_cave_normal"``).
        config: Pipeline configuration (uses ``max_working_resolution`` indirectly).
        photo_index: Unused for this step; present for API uniformity.

    Returns:
        Dict with keys ``width``, ``height``, ``format``, ``bit_depth``,
        ``orientation``.

    Raises:
        FileNotFoundError: If no matching upload key is found in storage.
    """
    from src.preprocessing.loader import load_image

    # Find the source key in uploads/
    source_key: Optional[str] = None
    for ext in _UPLOAD_EXTENSIONS:
        candidate = f"uploads/{stem}{ext}"
        if storage.exists(candidate):
            source_key = candidate
            break

    if source_key is None:
        raise FileNotFoundError(
            f"No uploaded file found for stem {stem!r}. "
            f"Expected one of: {[f'uploads/{stem}{e}' for e in _UPLOAD_EXTENSIONS]}"
        )

    logger.info("load: reading %s", source_key)
    # read_image() returns the processed float32 array.  We also need
    # ImageMetadata, so call load_image() on the resolved local path.
    # For Phase 2 (S3Storage), load_image() would be replaced by a
    # download-then-load pattern in the Lambda handler.
    image = storage.read_image(source_key)

    # Retrieve full metadata via load_image on the resolved local path.
    from src.storage.local import LocalStorage as _LS
    if isinstance(storage, _LS):
        local_path = str(storage._resolve(source_key))
    else:
        # Fallback: strip scheme from file:// URL (local only)
        url = storage.get_url(source_key)
        local_path = url.replace("file://", "")
    _, metadata = load_image(local_path)

    debug_key = f"debug/{stem}_01_loaded.jpg"
    storage.write_image(debug_key, image, format="jpeg", quality=95)
    logger.debug("load: wrote %s", debug_key)

    return {
        "width": metadata.original_size[0],
        "height": metadata.original_size[1],
        "format": metadata.format,
        "bit_depth": metadata.bit_depth,
        "orientation": metadata.orientation,
        "source_key": source_key,
    }
