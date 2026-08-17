"""Abstract StorageBackend protocol for pipeline I/O."""

from typing import Optional, Protocol

import numpy as np


class StorageBackend(Protocol):
    """Protocol defining the storage I/O contract for pipeline steps.

    Implementations: LocalStorage (CLI/macOS), S3Storage (Lambda/web).
    Keys use logical prefixes: ``uploads/``, ``debug/``, ``output/``.
    """

    def read_image(self, key: str) -> np.ndarray:
        """Read image from storage.

        Args:
            key: Storage key (e.g. ``debug/IMG_cave_01_loaded.jpg``).

        Returns:
            Float32 RGB array [0, 1], shape (H, W, 3).
        """
        ...

    def write_image(
        self,
        key: str,
        image: np.ndarray,
        format: str = "jpeg",
        quality: int = 95,
    ) -> str:
        """Write image to storage.

        Args:
            key: Storage key.
            image: Float32 RGB [0, 1] or uint8 RGB [0, 255].
            format: ``"jpeg"`` or ``"png"``.
            quality: JPEG quality (0–100), ignored for PNG.

        Returns:
            The key actually written (may have extension normalised).
        """
        ...

    def read_json(self, key: str) -> dict:
        """Read JSON metadata from storage.

        Args:
            key: Storage key (e.g. ``debug/IMG_cave_03_page_detection.json``).

        Returns:
            Parsed dict.
        """
        ...

    def write_json(self, key: str, data: dict) -> str:
        """Write JSON metadata to storage.

        Args:
            key: Storage key.
            data: Serialisable dict (numpy arrays are converted via ``.tolist()``).

        Returns:
            The key written.
        """
        ...

    def exists(self, key: str) -> bool:
        """Return True if *key* exists in storage."""
        ...

    def get_url(self, key: str) -> str:
        """Return an accessible URL for *key*.

        LocalStorage returns ``file://...``.  S3Storage returns a presigned URL.
        """
        ...

    def put_file(self, local_path: str, key: str) -> str:
        """Copy a local file into storage at *key*.

        Used by the CLI / Lambda handler to upload the original source file
        before invoking ``steps.load``.

        Args:
            local_path: Absolute path on the local filesystem.
            key: Destination storage key (e.g. ``uploads/IMG_cave.HEIC``).

        Returns:
            The key written.
        """
        ...
