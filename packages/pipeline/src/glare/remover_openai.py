"""OpenAI-based glare removal for the pipeline.

Adapts scripts/glare_remove.py into a pipeline-compatible module.
Works with numpy float32 RGB arrays [0, 1]; converts to/from temp PNG for the API.
"""

import base64
import io
import logging
import random
import tempfile
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 3
_RETRY_DELAY_RATE_LIMIT = (5, 10)   # seconds range for 429 rate-limit errors
_RETRY_DELAY_SERVER_ERROR = (3, 8)  # seconds range for 5xx server errors
_RETRY_DELAY_CONNECTION = (1, 5)    # seconds range for connection/timeout errors

# Allowed API sizes per OpenAI docs
_ALLOWED_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}


def _pick_api_size(w: int, h: int) -> str:
    """Select the closest allowed API output size based on image orientation.

    Args:
        w: Image width in pixels
        h: Image height in pixels

    Returns:
        API size string: "1536x1024" (landscape), "1024x1536" (portrait), or "1024x1024" (square)
    """
    if w > h:
        return "1536x1024"
    if h > w:
        return "1024x1536"
    return "1024x1024"


def _build_prompt(scene_desc: str) -> str:
    """Build the glare removal prompt for the OpenAI edit endpoint.

    Args:
        scene_desc: One-sentence description of the scene in the photo.

    Returns:
        Full prompt string.
    """
    return (
        "We used an iPhone camera to photograph a picture printed on glossy paper for digitization. "
        "Remove glare/reflections caused by the glossy surface. "
        "Preserve the original composition, geometry, textures, and colors. "
        "Only modify pixels necessary to remove glare/reflections; do not change framing. "
        f"Description of the printed photo: {scene_desc}"
    )


def _numpy_to_png_bytes(image: np.ndarray) -> bytes:
    """Convert float32 RGB numpy array to PNG bytes.

    Args:
        image: float32 RGB [0, 1], shape (H, W, 3)

    Returns:
        PNG file bytes
    """
    uint8 = (np.clip(image, 0, 1) * 255).astype(np.uint8)
    pil_img = Image.fromarray(uint8, mode="RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def _pil_to_numpy(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image to float32 RGB numpy array.

    Args:
        pil_img: PIL Image (any mode)

    Returns:
        float32 RGB [0, 1], shape (H, W, 3)
    """
    rgb = np.array(pil_img.convert("RGB"))
    return rgb.astype(np.float32) / 255.0


def _classify_openai_error(exc: Exception) -> Optional[tuple[int, int]]:
    """Classify an OpenAI exception and return a retry delay range (min, max) in seconds.

    Returns None for non-retriable errors (auth failures, bad requests, etc.).

    Args:
        exc: The exception raised by the OpenAI client.

    Returns:
        (min_delay, max_delay) tuple for retriable errors, or None to abort retries.
    """
    try:
        import openai
    except ImportError:
        # If openai isn't importable for type-checking, treat as retriable connection error
        return _RETRY_DELAY_CONNECTION

    if isinstance(exc, openai.RateLimitError):
        return _RETRY_DELAY_RATE_LIMIT
    if isinstance(exc, openai.InternalServerError):
        return _RETRY_DELAY_SERVER_ERROR
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return _RETRY_DELAY_CONNECTION
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError,
                         openai.BadRequestError, openai.NotFoundError)):
        return None  # Non-retriable — wrong key, bad input, etc.
    # Unknown OpenAI error: treat as retriable server-side issue
    if isinstance(exc, openai.OpenAIError):
        return _RETRY_DELAY_SERVER_ERROR
    # Non-OpenAI exception (e.g. network layer): retry with connection delay
    return _RETRY_DELAY_CONNECTION


def _call_openai_with_retry(
    client: "openai.OpenAI",
    tmp_path: Path,
    model: str,
    prompt: str,
    api_size: str,
    quality: str,
    input_fidelity: str,
) -> "openai.types.ImagesResponse":
    """Call client.images.edit with up to _MAX_RETRIES retries on transient errors.

    Args:
        client: Instantiated OpenAI client.
        tmp_path: Path to the temporary PNG file to send.
        model: OpenAI model name.
        prompt: Glare-removal prompt.
        api_size: API size string (e.g. "1536x1024").
        quality: API quality parameter.
        input_fidelity: API input_fidelity parameter.

    Returns:
        ImagesResponse from the API on success.

    Raises:
        Exception: The last exception after all retries are exhausted, or immediately
                   for non-retriable errors.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(1, _MAX_RETRIES + 2):  # attempts: 1 .. MAX_RETRIES+1
        try:
            with tmp_path.open("rb") as f:
                return client.images.edit(
                    model=model,
                    image=f,
                    prompt=prompt,
                    n=1,
                    size=api_size,
                    quality=quality,
                    input_fidelity=input_fidelity,
                    output_format="png",
                )
        except Exception as exc:
            last_exc = exc
            delay_range = _classify_openai_error(exc)

            if delay_range is None:
                # Non-retriable error — fail immediately
                logger.warning(f"OpenAI non-retriable error (attempt {attempt}): {exc}")
                raise

            if attempt > _MAX_RETRIES:
                # Exhausted all retries
                break

            delay = random.uniform(*delay_range)
            logger.warning(
                f"OpenAI API error (attempt {attempt}/{_MAX_RETRIES + 1}), "
                f"retrying in {delay:.1f}s: {exc}"
            )
            time.sleep(delay)

    raise last_exc  # type: ignore[misc]


def remove_glare_openai(
    image: np.ndarray,
    scene_desc: str,
    api_key: str,
    model: str = "gpt-image-1.5",
    quality: str = "high",
    input_fidelity: str = "high",
) -> np.ndarray:
    """Remove glare from a photo using OpenAI's image editing API.

    The input image is written to a temporary PNG, sent to the OpenAI
    ``images.edit`` endpoint with a glare-removal prompt, and the returned
    image is decoded back to a numpy array.

    Transient errors (rate-limit, server errors, connection issues) are retried
    up to ``_MAX_RETRIES`` times with a random delay (1–10 s, scaled by error
    type) between attempts. Non-retriable errors (bad auth, invalid request)
    fail immediately. If all retries are exhausted the original image is
    returned unchanged and a warning is logged so the pipeline never hard-fails
    on this step.

    Args:
        image: Input photo, float32 RGB [0, 1], shape (H, W, 3).
        scene_desc: One-sentence description of the scene (used in prompt).
        api_key: OpenAI API key.
        model: OpenAI image model to use. Default "gpt-image-1.5".
        quality: API quality parameter ("low", "medium", "high", "auto").
        input_fidelity: API input_fidelity parameter ("high" or "low").

    Returns:
        Glare-removed photo as float32 RGB [0, 1], shape may differ from input
        (API returns at most 1536×1024). Returns original image on failure.
    """
    h, w = image.shape[:2]
    api_size = _pick_api_size(w, h)
    prompt = _build_prompt(scene_desc)

    logger.debug(
        f"OpenAI glare removal: input={w}x{h}, api_size={api_size}, model={model}"
    )

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(_numpy_to_png_bytes(image))

        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        resp = _call_openai_with_retry(
            client=client,
            tmp_path=tmp_path,
            model=model,
            prompt=prompt,
            api_size=api_size,
            quality=quality,
            input_fidelity=input_fidelity,
        )

        b64 = resp.data[0].b64_json
        img_bytes = base64.b64decode(b64)
        result_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        result = _pil_to_numpy(result_pil)

        out_h, out_w = result.shape[:2]
        logger.info(
            f"OpenAI glare removal complete: {w}x{h} → {out_w}x{out_h}"
        )
        return result

    except Exception as e:
        logger.warning(
            f"OpenAI glare removal failed, returning original image unchanged: {e}"
        )
        return image

    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
