"""AI quality assessment and orientation correction using Claude vision API."""

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from anthropic import Anthropic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orientation correction
# ---------------------------------------------------------------------------

@dataclass
class PhotoAnalysis:
    """Result of a single Claude Vision call for orientation + scene description.

    rotation_degrees is the *clockwise* rotation to apply to make the photo
    correctly oriented (faces up, horizons horizontal, text readable).
    Valid values: 0, 90, 180, 270.
    """

    rotation_degrees: int          # 0, 90, 180, or 270 — clockwise to apply
    flip_horizontal: bool          # True only for genuine lateral mirror images
    orientation_confidence: str    # "low", "medium", or "high"
    scene_description: str         # One-sentence scene description for glare prompt


def _rotate_image(image: np.ndarray, degrees: int) -> np.ndarray:
    """Rotate image by a multiple of 90° with no interpolation.

    Args:
        image: float32 RGB [0, 1], shape (H, W, 3)
        degrees: Clockwise rotation in degrees — must be 0, 90, 180, or 270.

    Returns:
        Rotated image as float32 RGB [0, 1].
    """
    if degrees == 0:
        return image
    # np.rot90 rotates counter-clockwise; clockwise = negative k
    k = (360 - degrees) // 90
    return np.rot90(image, k=k)


def analyze_photo_for_processing(
    image: np.ndarray,
    api_key: Optional[str] = None,
    model: str = "claude-haiku-4-5-20251001",
) -> PhotoAnalysis:
    """Detect gross orientation error and generate a scene description.

    Makes a single Claude Vision call that returns:
    - The clockwise rotation needed to make the photo upright.
    - Whether a horizontal flip is needed (rare).
    - Confidence level in the orientation assessment.
    - A one-sentence scene description for use in the OpenAI glare prompt.

    Combining both into one call avoids paying double latency when OpenAI
    glare removal is also enabled.

    On any API failure the function returns a ``PhotoAnalysis`` with
    ``rotation_degrees=0``, ``flip_horizontal=False``, and
    ``orientation_confidence="low"`` so the caller can pass through unchanged.

    Args:
        image: Photo to analyse, float32 RGB [0, 1], shape (H, W, 3).
        api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env.
        model: Claude model to use. Defaults to Haiku (fast and cheap).

    Returns:
        PhotoAnalysis with orientation correction and scene description.
    """
    _passthrough = PhotoAnalysis(
        rotation_degrees=0,
        flip_horizontal=False,
        orientation_confidence="low",
        scene_description="",
    )

    # Resolve API key
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; skipping orientation analysis")
        return _passthrough

    image_b64 = _image_to_base64_jpeg(image, quality=85)

    prompt = (
        "You are examining a scanned or re-photographed physical print that may have "
        "been placed at an incorrect orientation.\n\n"
        "Orientation cues — check in this priority order:\n"
        "  1. PEOPLE / ANIMALS (most reliable): heads must be at the top, feet at the "
        "bottom. If you see people standing on their heads or hanging upside-down, "
        "the image needs a 180° rotation.\n"
        "  2. SKY / GROUND: sky belongs at the top, ground at the bottom.\n"
        "  3. HORIZON LINES: should run horizontally, not vertically.\n"
        "  4. READABLE TEXT: letters should read left-to-right.\n"
        "  ⚠ Do NOT use vehicle orientation as a cue — vehicles may legitimately be "
        "overturned or crashed in the scene itself.\n\n"
        "Step 1 — Apply the cues above (starting with people). "
        "Where is the CORRECT top of the scene in the image AS CURRENTLY SHOWN?\n"
        "  A) Already at the TOP edge      → correctly oriented\n"
        "  B) Currently at the BOTTOM edge → scene is upside-down (people are inverted)\n"
        "  C) Currently at the LEFT edge   → content rotated 90° clockwise\n"
        "  D) Currently at the RIGHT edge  → content rotated 90° counter-clockwise\n\n"
        "Step 2 — Map to the clockwise rotation to apply:\n"
        "  A → 0     B → 180     C → 90     D → 270\n\n"
        "Step 3 — Write a one-sentence description of what the scene shows.\n\n"
        "Reply with JSON only — no markdown, no extra text:\n"
        '{"rotation_degrees": <0|90|180|270>, "flip_horizontal": <true|false>, '
        '"confidence": <"low"|"medium"|"high">, "scene_description": "<one sentence>"}\n\n'
        "flip_horizontal is only true for a genuine lateral mirror image (a physical "
        "defect, extremely rare). When genuinely uncertain about orientation, use 0."
    )

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        response_text = response.content[0].text.strip()
        logger.info(f"Claude orientation response: {response_text}")

        # Strip optional markdown code fences
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        data = json.loads(response_text)

        rotation = int(data.get("rotation_degrees", 0))
        if rotation not in (0, 90, 180, 270):
            logger.warning(f"Unexpected rotation_degrees={rotation}, defaulting to 0")
            rotation = 0

        confidence = str(data.get("confidence", "low"))
        if confidence not in ("low", "medium", "high"):
            confidence = "low"

        result = PhotoAnalysis(
            rotation_degrees=rotation,
            flip_horizontal=bool(data.get("flip_horizontal", False)),
            orientation_confidence=confidence,
            scene_description=str(data.get("scene_description", "")).strip(),
        )

        logger.info(
            f"Orientation analysis: rotation={result.rotation_degrees}°, "
            f"flip={result.flip_horizontal}, confidence={result.orientation_confidence}"
        )
        return result

    except Exception as e:
        logger.warning(f"Orientation analysis failed, passing through: {e}")
        return _passthrough


def apply_orientation(image: np.ndarray, analysis: PhotoAnalysis) -> np.ndarray:
    """Apply the orientation correction described by a PhotoAnalysis.

    Only applied when confidence is "medium" or "high"; "low" is a passthrough.

    Args:
        image: float32 RGB [0, 1], shape (H, W, 3)
        analysis: Result from analyze_photo_for_processing()

    Returns:
        Orientation-corrected image (same dtype, possibly different shape).
    """
    if analysis.orientation_confidence == "low":
        logger.debug("Orientation confidence low; skipping correction")
        return image

    corrected = image
    if analysis.rotation_degrees != 0:
        corrected = _rotate_image(corrected, analysis.rotation_degrees)
        logger.debug(f"Applied {analysis.rotation_degrees}° clockwise rotation")

    if analysis.flip_horizontal:
        corrected = np.fliplr(corrected)
        logger.debug("Applied horizontal flip")

    return corrected


@dataclass
class QualityAssessment:
    """AI-based quality assessment result."""

    overall_score: float  # 1-10 scale
    glare_remaining: float  # 0-1 scale (0 = none, 1 = severe)
    artifacts_detected: bool
    sharpness_score: float  # 1-10 scale
    color_naturalness: float  # 1-10 scale
    notes: str
    confidence: float  # 0-1 scale (how confident the AI is)


def _image_to_base64_jpeg(image: np.ndarray, quality: int = 85) -> str:
    """Convert numpy image to base64-encoded JPEG.

    Args:
        image: RGB image, float32 [0, 1] or uint8 [0, 255]
        quality: JPEG quality (1-100)

    Returns:
        Base64-encoded JPEG string
    """
    from PIL import Image
    import io

    # Convert to uint8 if needed
    if image.dtype == np.float32 or image.dtype == np.float64:
        image_uint8 = (np.clip(image, 0, 1) * 255).astype(np.uint8)
    else:
        image_uint8 = image

    # Convert to PIL Image
    pil_image = Image.fromarray(image_uint8, mode='RGB')

    # Encode to JPEG in memory
    buffer = io.BytesIO()
    pil_image.save(buffer, format='JPEG', quality=quality)
    jpeg_bytes = buffer.getvalue()

    # Base64 encode
    return base64.b64encode(jpeg_bytes).decode('utf-8')


def assess_quality(
    original: np.ndarray,
    processed: np.ndarray,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-5-20250929"
) -> QualityAssessment:
    """Assess quality of processed image using Claude vision API.

    Args:
        original: Original image (after extraction, before restoration), RGB float32 [0, 1]
        processed: Processed image (after full pipeline), RGB float32 [0, 1]
        api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
        model: Claude model to use

    Returns:
        QualityAssessment with scores and notes

    Raises:
        ValueError: If API key not provided and not in environment
        RuntimeError: If API call fails
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError(
            "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
            "or pass api_key parameter."
        )

    # Convert images to base64 JPEG
    logger.debug("Converting images to base64 JPEG for API")
    original_b64 = _image_to_base64_jpeg(original, quality=92)
    processed_b64 = _image_to_base64_jpeg(processed, quality=92)

    # Create prompt
    prompt = """You are an expert photo restoration quality assessor. I'm showing you two images:
1. ORIGINAL: A photo extracted from an album page (may have glare, fading, color issues)
2. PROCESSED: The same photo after automated restoration (glare removal, color correction, sharpening)

Please assess the quality of the restoration and provide scores:

Analyze these aspects:
- **Glare removal**: Is glare successfully removed? Any remnants? Over-correction?
- **Artifacts**: Any halos, smears, unnatural transitions, or processing artifacts?
- **Sharpness**: Is the processed image appropriately sharp without over-sharpening?
- **Color naturalness**: Do colors look natural? Any color shifts or over-saturation?
- **Overall improvement**: Is the processed image clearly better than the original?

Respond in valid JSON format with these exact fields:
{
  "overall_score": <1-10, where 10 is perfect restoration>,
  "glare_remaining": <0-1, where 0 is no glare, 1 is severe glare still present>,
  "artifacts_detected": <true/false>,
  "sharpness_score": <1-10, where 10 is perfectly sharp, natural>,
  "color_naturalness": <1-10, where 10 is perfectly natural colors>,
  "notes": "<brief explanation of scores and any issues>",
  "confidence": <0-1, your confidence in this assessment>
}

Be critical but fair. A score of 7-8 is good, 9-10 is excellent."""

    try:
        # Initialize Anthropic client
        client = Anthropic(api_key=api_key)

        # Make API call
        logger.debug(f"Calling Claude API with model {model}")
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "ORIGINAL image:"
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": original_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": "PROCESSED image:"
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": processed_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        # Extract response text
        response_text = response.content[0].text
        logger.debug(f"Claude API response: {response_text}")

        # Parse JSON response
        # Claude may wrap JSON in markdown code blocks, so extract it
        if "```json" in response_text:
            # Extract JSON from markdown code block
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            # Generic code block
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_text = response_text[json_start:json_end].strip()
        else:
            json_text = response_text.strip()

        result = json.loads(json_text)

        # Create QualityAssessment object
        assessment = QualityAssessment(
            overall_score=float(result['overall_score']),
            glare_remaining=float(result['glare_remaining']),
            artifacts_detected=bool(result['artifacts_detected']),
            sharpness_score=float(result['sharpness_score']),
            color_naturalness=float(result['color_naturalness']),
            notes=str(result['notes']),
            confidence=float(result['confidence'])
        )

        logger.info(
            f"AI quality assessment: overall={assessment.overall_score:.1f}/10, "
            f"confidence={assessment.confidence:.2f}"
        )

        return assessment

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude API response as JSON: {e}")
        logger.error(f"Response text: {response_text}")
        raise RuntimeError(f"Failed to parse AI response: {e}")

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise RuntimeError(f"AI quality assessment failed: {e}")


def assess_quality_batch(
    image_pairs: list[Tuple[np.ndarray, np.ndarray]],
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-5-20250929"
) -> list[QualityAssessment]:
    """Assess quality for multiple image pairs.

    Args:
        image_pairs: List of (original, processed) tuples
        api_key: Anthropic API key
        model: Claude model to use

    Returns:
        List of QualityAssessment objects
    """
    results = []

    for i, (original, processed) in enumerate(image_pairs, 1):
        logger.info(f"Assessing image pair {i}/{len(image_pairs)}")
        try:
            assessment = assess_quality(original, processed, api_key, model)
            results.append(assessment)
        except Exception as e:
            logger.error(f"Failed to assess image pair {i}: {e}")
            # Create a default assessment indicating failure
            results.append(QualityAssessment(
                overall_score=0.0,
                glare_remaining=0.0,
                artifacts_detected=False,
                sharpness_score=0.0,
                color_naturalness=0.0,
                notes=f"Assessment failed: {e}",
                confidence=0.0
            ))

    return results
