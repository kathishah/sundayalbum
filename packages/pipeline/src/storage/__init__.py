"""Storage backends for pipeline I/O abstraction.

Exports:
    StorageBackend  — Protocol (structural typing)
    LocalStorage    — Filesystem implementation (CLI / macOS app)
    get_backend     — Factory helper
"""

from src.storage.backend import StorageBackend
from src.storage.local import LocalStorage
from src.storage.s3 import S3Storage


def get_backend(backend_type: str = "local", **kwargs: object) -> StorageBackend:
    """Return a StorageBackend instance by type.

    Args:
        backend_type: ``"local"`` (default) or ``"s3"``.
        **kwargs: Passed to the backend constructor.

    Returns:
        A StorageBackend instance.

    Raises:
        ValueError: If *backend_type* is not recognised.
    """
    if backend_type == "local":
        return LocalStorage(**kwargs)  # type: ignore[arg-type]
    if backend_type == "s3":
        return S3Storage(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"Unknown backend type: {backend_type!r}")


__all__ = ["StorageBackend", "LocalStorage", "S3Storage", "get_backend"]
