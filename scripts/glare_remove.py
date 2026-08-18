#!/Users/dev/dev/sundayalbum/.venv/bin/python3
"""
glare_remove.py

Creates output(s) from one input image:
1) OpenCV baseline (optional) — NOT great for glossy glare, included for comparison
2) OpenAI Images Edit (mask-free) — prompt-driven glare removal

Doc-compliant changes:
- Uses client.images.edit(...)
- DOES NOT pass unsupported args like `moderation`
- Uses only allowed `size` values: "1024x1024", "1536x1024", "1024x1536", or "auto"
- Prints:
  - original input size
  - chosen API size
  - processed output size

Requirements:
  pip install opencv-python-headless numpy pillow openai httpx

Secrets:
  secrets.json containing:
    {"OPENAI_API_KEY": "sk-..."}  (also accepts openai_api_key/api_key/key)

Usage:
  ./scripts/glare_remove.py input.jpg --outdir out --openai --scene-desc "..." --size-mode orient
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
from PIL import Image
import cv2


# ----------------------------
# Limits / validation
# ----------------------------

MAX_FILE_SIZE_MB = 50
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def validate_image_for_api(path: Path) -> Tuple[int, int]:
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"File size {size_mb:.2f} MB exceeds limit of {MAX_FILE_SIZE_MB} MB.")

    try:
        with Image.open(path) as im:
            w, h = im.size
    except Exception as e:
        raise ValueError(f"Image not readable by PIL: {e}")

    return w, h


# ----------------------------
# Secrets
# ----------------------------

def load_openai_key(secrets_path: Path) -> str:
    if not secrets_path.exists():
        raise FileNotFoundError(f"secrets.json not found at: {secrets_path}")

    data = json.loads(secrets_path.read_text(encoding="utf-8"))
    for k in ("OPENAI_API_KEY", "openai_api_key", "api_key", "key"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    raise KeyError(
        "Could not find API key in secrets.json. Expected one of: "
        "OPENAI_API_KEY, openai_api_key, api_key, key"
    )


# ----------------------------
# OpenCV baseline (optional)
# ----------------------------

def pil_to_bgr(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def build_bright_spot_mask(bgr: np.ndarray, v_thresh: int = 245) -> np.ndarray:
    """Baseline-only: flags very bright pixels (often NOT the same as glossy glare)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    _, _, v = cv2.split(hsv)
    mask = (v >= v_thresh).astype(np.uint8) * 255
    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=1)
    return mask


def opencv_inpaint(bgr: np.ndarray, mask_255: np.ndarray, radius: float = 5.0) -> np.ndarray:
    return cv2.inpaint(bgr, mask_255, float(radius), cv2.INPAINT_TELEA)


# ----------------------------
# OpenAI edit (mask-free)
# ----------------------------

ALLOWED_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}


def pick_api_size(orig_w: int, orig_h: int, size_mode: str) -> str:
    """
    size_mode:
      - "auto": pass "auto"
      - "orient": choose 1536x1024 for landscape, 1024x1536 for portrait, 1024x1024 for square-ish
      - "landscape": force 1536x1024
      - "portrait": force 1024x1536
      - "square": force 1024x1024
    """
    size_mode = size_mode.lower().strip()

    if size_mode == "auto":
        return f"auto"

    if size_mode == "landscape":
        return "1536x1024"
    if size_mode == "portrait":
        return "1024x1536"
    if size_mode == "square":
        return "1024x1024"

    # default: orient
    if orig_w > orig_h:
        return "1536x1024"
    if orig_h > orig_w:
        return "1024x1536"
    return "1024x1024"


def build_prompt(scene_desc: str) -> str:
    # Your prompt intent, tightened to reduce drift:
    return (
        "We used an iPhone camera to photograph a picture printed on glossy paper for digitization. "
        "Remove glare/reflections caused by the glossy surface. "
        "Preserve the original composition, geometry, textures, and colors. "
        "Only modify pixels necessary to remove glare/reflections; do not change framing. "
        f"Description of the printed photo: {scene_desc}"
    )


def openai_edit_remove_glare(
    api_key: str,
    input_path: Path,
    prompt: str,
    model: str,
    size: str,
    n: int = 1,
    quality: str = "high",
    background: str = "auto",
    input_fidelity: str = "high",
    output_format: str = "png",
) -> Image.Image:
    """
    Calls OpenAI Images Edit endpoint (mask optional; here mask-free).
    NOTE: Do NOT pass 'moderation' here; the SDK will reject it.
    """
    from openai import OpenAI

    if size not in ALLOWED_SIZES:
        raise ValueError(f"Invalid size '{size}'. Allowed: {', '.join(sorted(ALLOWED_SIZES))}")

    client = OpenAI(api_key=api_key)

    with input_path.open("rb") as f:
        resp = client.images.edit(
            model=model,
            image=f,
            prompt=prompt,
            n=n,
            size=size,
            quality=quality,
            background=background,
            input_fidelity=input_fidelity,
            output_format=output_format,
        )

    b64 = resp.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to input image (png/jpg/jpeg/webp)")
    ap.add_argument("--outdir", default=".", help="Output directory")
    ap.add_argument("--prefix", default=None, help="Output filename prefix (default: input stem)")

    # OpenCV baseline
    ap.add_argument("--opencv", action="store_true", help="Generate OpenCV baseline output")
    ap.add_argument("--opencv-vthresh", type=int, default=245, help="OpenCV baseline V threshold")
    ap.add_argument("--opencv-radius", type=float, default=5.0, help="OpenCV inpaint radius")

    # OpenAI
    ap.add_argument("--openai", action="store_true", help="Generate OpenAI output")
    ap.add_argument("--secrets", default="secrets.json", help="Path to secrets.json")
    ap.add_argument("--model", default="gpt-image-1.5", help="OpenAI image model (e.g., gpt-image-1.5)")
    ap.add_argument("--scene-desc", default="", help="One-sentence scene description")
    ap.add_argument("--n", type=int, default=1, help="Number of images to generate")
    ap.add_argument("--output-format", default="png", choices=["png", "jpeg", "webp"], help="Output format")

    # Playground-like params (no moderation)
    ap.add_argument("--quality", default="high", choices=["auto", "low", "medium", "high", "standard"])
    ap.add_argument("--background", default="auto", choices=["auto", "transparent", "opaque"])
    ap.add_argument("--input-fidelity", default="high", choices=["high", "low"])

    # Size selection
    ap.add_argument(
        "--size-mode",
        default="orient",
        choices=["auto", "orient", "landscape", "portrait", "square"],
        help="How to pick the API size. Uses allowed sizes only.",
    )

    args = ap.parse_args()

    in_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix if args.prefix else in_path.stem

    # Validate file meets basic API expectations
    try:
        orig_w, orig_h = validate_image_for_api(in_path)
    except Exception as e:
        print(f"[ERROR] Validation failed: {e}")
        sys.exit(1)

    print(f"[INFO] Original image size: {orig_w}x{orig_h}")

    # Load image once for OpenCV baseline
    pil_img = Image.open(in_path).convert("RGB")

    # OpenCV baseline (optional)
    if args.opencv:
        bgr = pil_to_bgr(pil_img)
        mask = build_bright_spot_mask(bgr, v_thresh=args.opencv_vthresh)
        out_bgr = opencv_inpaint(bgr, mask, radius=args.opencv_radius)
        out_pil = bgr_to_pil(out_bgr)
        opencv_path = outdir / f"{prefix}_opencv.png"
        out_pil.save(opencv_path)
        print(f"[OK] OpenCV output: {opencv_path}")

    # OpenAI output (optional)
    if args.openai:
        api_key = load_openai_key(Path(args.secrets))

        api_size = pick_api_size(orig_w, orig_h, args.size_mode)
        print(f"[INFO] Picked API size: {api_size}")

        scene = args.scene_desc.strip() or "A photographed image."
        prompt = build_prompt(scene)

        ai_img = openai_edit_remove_glare(
            api_key=api_key,
            input_path=in_path,
            prompt=prompt,
            model=args.model,
            size=api_size,
            n=args.n,
            quality=args.quality,
            background=args.background,
            input_fidelity=args.input_fidelity,
            output_format=args.output_format,
        )

        out_w, out_h = ai_img.size
        print(f"[INFO] Processed image size: {out_w}x{out_h}")

        ext = "jpg" if args.output_format == "jpeg" else args.output_format
        openai_path = outdir / f"{prefix}_openai.{ext}"
        ai_img.save(openai_path)
        print(f"[OK] OpenAI output: {openai_path}")

    if not args.opencv and not args.openai:
        print("[INFO] Nothing to do. Use --opencv and/or --openai.")


if __name__ == "__main__":
    main()

