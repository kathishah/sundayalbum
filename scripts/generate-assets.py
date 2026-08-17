#!/usr/bin/env python3
"""
generate-assets.py — Generate Sunday Album app icon + DMG background.

Outputs:
  apps/mac/SundayAlbum/Assets.xcassets/AppIcon.appiconset/   (all 9 icon sizes)
  apps/mac/assets/dmg-background@2x.png                      (1320x800 Retina DMG bg)
  apps/mac/assets/dmg-background.png                         (660x400 1x fallback)

Run from repo root:
  source .venv/bin/activate
  python scripts/generate-assets.py
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

# ── Repo paths ──────────────────────────────────────────────────────────────
REPO = Path(__file__).parent.parent
ICON_DIR = REPO / "apps/mac/SundayAlbum/Assets.xcassets/AppIcon.appiconset"
ASSETS_DIR = REPO / "apps/mac/assets"
ICON_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ── Brand colours ────────────────────────────────────────────────────────────
AMBER_DARK  = (180,  83,   9)   # #B45309
AMBER_MID   = (217, 119,   6)   # #D97706
AMBER_LIGHT = (245, 158,  11)   # #F59E0B
CREAM       = (255, 248, 240)   # #FFF8F0
WARM_WHITE  = (255, 253, 250)
STONE_800   = ( 28,  25,  23)   # #1C1917  (dark bg)
WHITE       = (255, 255, 255)
SHADOW      = (  0,   0,   0, 60)

# ═══════════════════════════════════════════════════════════════════════════
# APP ICON
# ═══════════════════════════════════════════════════════════════════════════

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def make_icon(size: int) -> Image.Image:
    """Render one app icon at `size`×`size` px (transparent background)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = size * 0.06
    r   = size * 0.22          # corner radius (macOS squircle approximation)

    # ── Amber gradient background ─────────────────────────────────────────
    # Fake vertical gradient with horizontal bands
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    for y in range(size):
        t   = y / size
        col = lerp_color(AMBER_LIGHT, AMBER_DARK, t)
        bg_draw.line([(0, y), (size, y)], fill=col + (255,))
    # Clip gradient to rounded rect
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([pad, pad, size - pad, size - pad],
                                 radius=r, fill=255)
    img.paste(bg, mask=mask)

    # ── Stacked photo prints motif ────────────────────────────────────────
    # Three overlapping white rectangles (photo prints) rotated slightly
    cx, cy = size / 2, size / 2
    photo_w = size * 0.42
    photo_h = size * 0.34

    def draw_photo_print(angle_deg, offset_x, offset_y, alpha=220):
        """Draw a rotated white rectangle representing a photo print."""
        ph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ph_draw = ImageDraw.Draw(ph)
        x0 = cx - photo_w / 2 + offset_x
        y0 = cy - photo_h / 2 + offset_y
        x1 = cx + photo_w / 2 + offset_x
        y1 = cy + photo_h / 2 + offset_y
        # Border radius proportional to photo size
        br = photo_w * 0.06
        ph_draw.rounded_rectangle([x0, y0, x1, y1],
                                   radius=br,
                                   fill=(255, 255, 255, alpha))
        ph = ph.rotate(angle_deg, center=(cx, cy), resample=Image.BICUBIC,
                       expand=False)
        img.alpha_composite(ph)

    # Back print (rotated left, offset down-right)
    draw_photo_print(-12, size * 0.06, size * 0.06, alpha=160)
    # Middle print (rotated right, offset up-left)
    draw_photo_print(8, -size * 0.04, -size * 0.04, alpha=190)
    # Front print (straight, centered, fully opaque)
    draw_photo_print(0, 0, 0, alpha=240)

    # ── Subtle amber sun streak behind the prints ─────────────────────────
    # Small warm circle at top-right of front print
    sun_r = size * 0.07
    sun_x = cx + photo_w * 0.28
    sun_y = cy - photo_h * 0.28
    sun_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sun_draw  = ImageDraw.Draw(sun_layer)
    sun_draw.ellipse(
        [sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r],
        fill=AMBER_LIGHT + (200,)
    )
    sun_layer = sun_layer.filter(ImageFilter.GaussianBlur(size * 0.04))
    img.alpha_composite(sun_layer)

    return img


# macOS required icon sizes: (logical_size, scale)
ICON_SIZES = [
    (16,  1), (16,  2),
    (32,  1), (32,  2),
    (128, 1), (128, 2),
    (256, 1), (256, 2),
    (512, 1), (512, 2),
]

icons_json = []
for logical, scale in ICON_SIZES:
    px       = logical * scale
    filename = f"icon_{logical}x{logical}@{scale}x.png" if scale > 1 \
               else f"icon_{logical}x{logical}.png"
    icon     = make_icon(px)
    icon.save(ICON_DIR / filename)
    icons_json.append({
        "filename": filename,
        "idiom":    "mac",
        "scale":    f"{scale}x",
        "size":     f"{logical}x{logical}",
    })
    print(f"  icon  {px:4d}×{px:<4d}  →  {filename}")

# Write Contents.json
import json
contents = {
    "images": [
        {
            "filename": e["filename"],
            "idiom":    e["idiom"],
            "scale":    e["scale"],
            "size":     e["size"],
        }
        for e in icons_json
    ],
    "info": {"author": "xcode", "version": 1},
}
(ICON_DIR / "Contents.json").write_text(
    json.dumps(contents, indent=2) + "\n"
)
print(f"\n✓ App icon → {ICON_DIR.relative_to(REPO)}/")


# ═══════════════════════════════════════════════════════════════════════════
# DMG BACKGROUND  (660×400 logical → render @2x = 1320×800)
# ═══════════════════════════════════════════════════════════════════════════

DMG_W, DMG_H = 660, 400     # logical points (matches --window-size in create-dmg)
SCALE         = 2            # Retina
PW, PH        = DMG_W * SCALE, DMG_H * SCALE


def draw_dmg_background() -> Image.Image:
    img  = Image.new("RGBA", (PW, PH), WARM_WHITE + (255,))
    draw = ImageDraw.Draw(img)

    # ── Subtle warm gradient overlay ──────────────────────────────────────
    for y in range(PH):
        t = y / PH
        col = lerp_color((255, 252, 245), (255, 245, 228), t)
        draw.line([(0, y), (PW, y)], fill=col + (255,))

    # ── Soft amber glow at top-centre ─────────────────────────────────────
    glow = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    gd.ellipse([PW // 2 - 300, -200, PW // 2 + 300, 400],
               fill=AMBER_LIGHT + (40,))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img.alpha_composite(glow)

    # ── Title "Sunday Album" ──────────────────────────────────────────────
    # Draw text using basic PIL (no custom font bundled in script)
    title    = "Sunday Album"
    t_size   = 52            # px at @2x
    t_y      = 56

    # Use a simple proportional rendering: draw amber filled rounded label
    label_w  = len(title) * t_size // 2 + 40
    label_h  = t_size + 20
    label_x  = (PW - label_w) // 2
    draw.rounded_rectangle(
        [label_x, t_y, label_x + label_w, t_y + label_h],
        radius=label_h // 2,
        fill=AMBER_MID + (18,),
    )
    # Text itself (PIL default font — Fraunces not guaranteed in env)
    try:
        from PIL import ImageFont
        font_path = "/System/Library/Fonts/Supplemental/Futura.ttc"
        font      = ImageFont.truetype(font_path, t_size)
    except Exception:
        font = None  # falls back to default bitmap font

    text_bbox = draw.textbbox((0, 0), title, font=font)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]
    tx = (PW - tw) // 2
    ty = t_y + (label_h - th) // 2
    draw.text((tx, ty), title, fill=AMBER_DARK + (255,), font=font)

    # ── Drag-here instruction ─────────────────────────────────────────────
    instruction = "Drag Sunday Album to Applications to install"
    try:
        small_font = ImageFont.truetype(font_path, 28) if font else None
    except Exception:
        small_font = None
    ib = draw.textbbox((0, 0), instruction, font=small_font)
    iw = ib[2] - ib[0]
    draw.text(
        ((PW - iw) // 2, t_y + label_h + 28),
        instruction,
        fill=(120, 100, 80, 200),
        font=small_font,
    )

    # ── Arrow from app drop zone to Applications drop zone ────────────────
    # App icon sits at ~(180, 210) logical → (360, 420) @2x
    # Applications folder at ~(480, 210) logical → (960, 420) @2x
    ax0, ay0 = 380, 420    # arrow start (right edge of app zone)
    ax1, ay1 = 940, 420    # arrow end (left edge of Applications zone)
    shaft_y  = ay0

    # Shaft
    draw.line([(ax0, shaft_y), (ax1, shaft_y)],
              fill=AMBER_MID + (160,), width=6)
    # Arrowhead
    ah = 18
    draw.polygon(
        [(ax1, shaft_y),
         (ax1 - ah, shaft_y - ah),
         (ax1 - ah, shaft_y + ah)],
        fill=AMBER_MID + (200,),
    )

    # ── Drop zone labels ──────────────────────────────────────────────────
    label_y = 520
    try:
        label_font = ImageFont.truetype(font_path, 26) if font else None
    except Exception:
        label_font = None

    for text, cx_logical in [("SundayAlbum.app", 180), ("Applications", 480)]:
        lb  = draw.textbbox((0, 0), text, font=label_font)
        lw  = lb[2] - lb[0]
        draw.text(
            (cx_logical * SCALE - lw // 2, label_y),
            text,
            fill=(100, 80, 60, 180),
            font=label_font,
        )

    return img.convert("RGB")


dmg_bg = draw_dmg_background()
path_2x = ASSETS_DIR / "dmg-background@2x.png"
path_1x = ASSETS_DIR / "dmg-background.png"
dmg_bg.save(path_2x)
dmg_bg.resize((DMG_W, DMG_H), Image.LANCZOS).save(path_1x)
print(f"✓ DMG bg   → {path_2x.relative_to(REPO)}")
print(f"✓ DMG bg   → {path_1x.relative_to(REPO)}")
print("\nAll assets generated.")
