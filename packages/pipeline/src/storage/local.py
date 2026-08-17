"""Local filesystem storage backend."""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class LocalStorage:
    """Local filesystem implementation of StorageBackend.

    Keys use logical prefixes (``uploads/``, ``debug/``, ``output/``) that are
    mapped to concrete directories:

    * ``uploads/*`` → ``<base_dir>/uploads/*``
    * ``debug/*``   → ``<debug_dir>/*``   (defaults to ``<base_dir>/debug/``)
    * ``output/*``  → ``<output_dir>/*``  (defaults to ``<base_dir>/output/``)
    * anything else → ``<base_dir>/<key>``

    This lets the CLI pass custom ``--output`` / ``--debug-dir`` directories
    while keeping the storage abstraction consistent with the S3 layout.
    """

    def __init__(
        self,
        base_dir: Union[str, Path],
        debug_dir: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialise LocalStorage.

        Args:
            base_dir: Root directory.  ``uploads/`` lives here.
            debug_dir: Directory for ``debug/*`` keys.
                       Defaults to ``<base_dir>/debug/``.
            output_dir: Directory for ``output/*`` keys.
                        Defaults to ``<base_dir>/output/``.
        """
        self._base = Path(base_dir)
        self._debug = Path(debug_dir) if debug_dir else self._base / "debug"
        self._output = Path(output_dir) if output_dir else self._base / "output"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Resolve a logical key to an absolute filesystem path."""
        if key.startswith("debug/"):
            return self._debug / key[len("debug/"):]
        if key.startswith("output/"):
            return self._output / key[len("output/"):]
        if key.startswith("uploads/"):
            return self._base / key
        return self._base / key

    def _ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # StorageBackend protocol
    # ------------------------------------------------------------------

    def read_image(self, key: str) -> np.ndarray:
        """Read image from local filesystem.

        Delegates to ``src.preprocessing.loader.load_image`` so HEIC / DNG
        files in ``uploads/`` are decoded correctly.

        Returns:
            Float32 RGB [0, 1], shape (H, W, 3).
        """
        from src.preprocessing.loader import load_image

        path = self._resolve(key)
        image, _ = load_image(str(path))
        return image

    def write_image(
        self,
        key: str,
        image: np.ndarray,
        format: str = "jpeg",
        quality: int = 95,
    ) -> str:
        """Write image to local filesystem.

        Args:
            key: Storage key.
            image: Float32 RGB [0, 1] or uint8 RGB.
            format: ``"jpeg"`` or ``"png"``.
            quality: JPEG quality (ignored for PNG).

        Returns:
            Key written (extension may be normalised).
        """
        path = self._resolve(key)

        # Normalise extension to match format
        if format == "jpeg":
            path = path.with_suffix(".jpg")
            key = _set_suffix(key, ".jpg")
        elif format == "png":
            path = path.with_suffix(".png")
            key = _set_suffix(key, ".png")

        self._ensure_parent(path)

        # Convert to uint8
        if image.dtype in (np.float32, np.float64):
            img_u8 = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
        else:
            img_u8 = image.astype(np.uint8)

        # Convert RGB → BGR for OpenCV
        if img_u8.ndim == 2:
            img_bgr = cv2.cvtColor(img_u8, cv2.COLOR_GRAY2BGR)
        elif img_u8.shape[2] == 4:
            img_bgr = cv2.cvtColor(img_u8, cv2.COLOR_RGBA2BGR)
        else:
            img_bgr = cv2.cvtColor(img_u8, cv2.COLOR_RGB2BGR)

        if format == "jpeg":
            cv2.imwrite(str(path), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        else:
            # PNG compression level 1: fast write, reasonable size
            cv2.imwrite(str(path), img_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 1])

        logger.debug("Written: %s", path)
        return key

    def read_json(self, key: str) -> dict:
        """Read JSON from local filesystem."""
        path = self._resolve(key)
        return json.loads(path.read_text())

    def write_json(self, key: str, data: dict) -> str:
        """Write JSON to local filesystem.

        Returns:
            Key written.
        """
        path = self._resolve(key)
        self._ensure_parent(path)
        path.write_text(json.dumps(data, indent=2, default=_json_default))
        logger.debug("Written: %s", path)
        return key

    def exists(self, key: str) -> bool:
        """Return True if the resolved path exists."""
        return self._resolve(key).exists()

    def get_url(self, key: str) -> str:
        """Return a ``file://`` URL for the given key."""
        return f"file://{self._resolve(key).absolute()}"

    def put_file(self, local_path: str, key: str) -> str:
        """Copy *local_path* into storage at *key*.

        Args:
            local_path: Source path on the local filesystem.
            key: Destination storage key.

        Returns:
            Key written.
        """
        dest = self._resolve(key)
        self._ensure_parent(dest)
        shutil.copy2(local_path, dest)
        logger.debug("put_file: %s → %s", local_path, dest)
        return key


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _set_suffix(key: str, suffix: str) -> str:
    """Return *key* with its extension replaced by *suffix*."""
    p = Path(key)
    return str(p.with_suffix(suffix))


def _json_default(obj: object) -> object:
    """JSON serialiser for numpy scalars and arrays."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    raise TypeError(f"Not JSON serialisable: {type(obj)}")
