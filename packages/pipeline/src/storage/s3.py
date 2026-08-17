"""S3 storage backend for Sunday Album pipeline (Lambda / web path)."""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import boto3
import numpy as np
from botocore.config import Config
from PIL import Image

logger = logging.getLogger(__name__)

_REGION = os.environ.get("AWS_DEPLOY_REGION", "us-west-2")


def _make_s3_client(region: str = _REGION):
    """Return a boto3 S3 client configured for regional endpoint + SigV4."""
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


class S3Storage:
    """S3 implementation of the StorageBackend protocol.

    ``key`` values follow the same logical prefix convention as
    ``LocalStorage``: ``uploads/``, ``debug/``, ``output/``.
    Each key is stored in S3 under ``{prefix}/{key}``.

    Example::

        storage = S3Storage(
            bucket="sundayalbum-data-123456789012-us-west-2",
            prefix="f1ceafcd...",    # SHA-256 of user email
        )
        image = storage.read_image("uploads/IMG_cave_normal.HEIC")
        # → downloads s3://bucket/f1ceafcd.../uploads/IMG_cave_normal.HEIC

    Args:
        bucket: S3 bucket name.
        prefix: User-scoped prefix (SHA-256 hash of email, no trailing slash).
        region: AWS region (default: ``AWS_DEPLOY_REGION`` env var).
    """

    def __init__(self, bucket: str, prefix: str, region: str = _REGION) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._region = region
        self._s3 = _make_s3_client(region)

    # ── Key helpers ───────────────────────────────────────────────────────────

    def _full_key(self, key: str) -> str:
        """Return the full S3 object key for a logical storage key."""
        return f"{self._prefix}/{key}"

    # ── StorageBackend protocol ───────────────────────────────────────────────

    def read_image(self, key: str) -> np.ndarray:
        """Download from S3 and decode to float32 RGB [0, 1].

        HEIC files are decoded via ``pillow-heif`` (bundled wheels, no libheif
        system package needed on Lambda Linux).  JPEG/PNG are decoded via PIL.

        Args:
            key: Logical storage key, e.g. ``"uploads/IMG_cave_normal.HEIC"``.

        Returns:
            Float32 RGB array [0, 1], shape (H, W, 3).

        Raises:
            FileNotFoundError: If the S3 object does not exist.
        """
        full_key = self._full_key(key)
        ext = Path(key).suffix.lower()

        # Download to /tmp so format-specific decoders can use a file path
        suffix = ext if ext else ".bin"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(tmp_fd)

        try:
            logger.debug("S3 download: s3://%s/%s → %s", self._bucket, full_key, tmp_path)
            self._s3.download_file(self._bucket, full_key, tmp_path)
            arr = _decode_image(tmp_path, ext)
        except self._s3.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchKey"):
                raise FileNotFoundError(
                    f"S3 key not found: s3://{self._bucket}/{full_key}"
                ) from exc
            raise
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return arr

    def write_image(
        self,
        key: str,
        image: np.ndarray,
        format: str = "jpeg",
        quality: int = 95,
    ) -> str:
        """Encode image and upload to S3.

        Args:
            key: Logical storage key.
            image: Float32 RGB [0, 1] or uint8 RGB [0, 255].
            format: ``"jpeg"`` or ``"png"``.
            quality: JPEG quality (ignored for PNG).

        Returns:
            The key actually written (extension normalised).
        """
        # Normalise extension
        if format == "jpeg":
            key = _set_suffix(key, ".jpg")
            content_type = "image/jpeg"
        else:
            key = _set_suffix(key, ".png")
            content_type = "image/png"

        full_key = self._full_key(key)

        # Convert to uint8
        if image.dtype in (np.float32, np.float64):
            img_u8 = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
        else:
            img_u8 = image.astype(np.uint8)

        # PIL encode → bytes in memory (no temp file needed for output)
        pil_img = Image.fromarray(img_u8, mode="RGB")
        buf = io.BytesIO()
        if format == "jpeg":
            pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
        else:
            pil_img.save(buf, format="PNG", compress_level=1)
        buf.seek(0)
        data = buf.getvalue()

        self._s3.put_object(
            Bucket=self._bucket,
            Key=full_key,
            Body=data,
            ContentType=content_type,
        )
        logger.debug("S3 write: s3://%s/%s (%d bytes)", self._bucket, full_key, len(data))
        return key

    def read_json(self, key: str) -> dict:
        """Download and parse a JSON object from S3.

        Returns:
            Parsed dict.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        full_key = self._full_key(key)
        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=full_key)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except self._s3.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchKey"):
                raise FileNotFoundError(
                    f"S3 key not found: s3://{self._bucket}/{full_key}"
                ) from exc
            raise

    def write_json(self, key: str, data: dict) -> str:
        """Serialise dict to JSON and upload to S3.

        Numpy arrays and scalars are serialised via a custom encoder.

        Returns:
            The key written.
        """
        full_key = self._full_key(key)
        body = json.dumps(data, indent=2, default=_json_default).encode("utf-8")
        self._s3.put_object(
            Bucket=self._bucket,
            Key=full_key,
            Body=body,
            ContentType="application/json",
        )
        logger.debug("S3 write JSON: s3://%s/%s", self._bucket, full_key)
        return key

    def exists(self, key: str) -> bool:
        """Return True if the S3 object exists."""
        full_key = self._full_key(key)
        try:
            self._s3.head_object(Bucket=self._bucket, Key=full_key)
            return True
        except Exception:
            return False

    def get_url(self, key: str, expires: int = 3600) -> str:
        """Return a presigned GET URL valid for *expires* seconds."""
        full_key = self._full_key(key)
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": full_key},
            ExpiresIn=expires,
        )

    def put_file(self, local_path: str, key: str) -> str:
        """Upload a local file to S3 at *key*.

        Args:
            local_path: Absolute path on the local filesystem.
            key: Destination logical key.

        Returns:
            The key written.
        """
        full_key = self._full_key(key)
        self._s3.upload_file(local_path, self._bucket, full_key)
        logger.debug("S3 put_file: %s → s3://%s/%s", local_path, self._bucket, full_key)
        return key

    def download_local(self, key: str, local_path: str) -> str:
        """Download S3 object to a specific local path.

        Used by ``handlers/load.py`` to get the source file path so that
        ``src.preprocessing.loader.load_image()`` can read format metadata.

        Args:
            key: Logical storage key.
            local_path: Destination path on the local filesystem.

        Returns:
            *local_path* (for chaining).
        """
        full_key = self._full_key(key)
        self._s3.download_file(self._bucket, full_key, local_path)
        return local_path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _decode_image(path: str, ext: str) -> np.ndarray:
    """Decode image file at *path* to float32 RGB [0, 1]."""
    if ext in (".heic", ".heif"):
        from pillow_heif import register_heif_opener
        register_heif_opener()

    img = Image.open(path).convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    return arr


def _set_suffix(key: str, suffix: str) -> str:
    """Return *key* with its extension replaced by *suffix*."""
    return str(Path(key).with_suffix(suffix))


def _json_default(obj: object) -> object:
    """JSON encoder for numpy types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    raise TypeError(f"Not JSON-serialisable: {type(obj)}")
