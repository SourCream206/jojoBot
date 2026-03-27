"""
utils/image_effects.py
Image processing utilities for adding visual effects to stand cards.
"""

import io
import logging
import math
import aiohttp
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance

log = logging.getLogger("jojo-rpg")

# Cache to avoid re-processing the same images
_GLOW_CACHE: dict[str, bytes] = {}
MAX_CACHE_SIZE = 50


async def fetch_image(url: str) -> Image.Image | None:
    """Fetch an image from a URL and return as PIL Image."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    log.warning(f"Failed to fetch image: HTTP {resp.status}")
                    return None
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception as e:
        log.warning(f"Failed to fetch image: {e}")
        return None


def add_solar_flare_explosion(img: Image.Image) -> Image.Image:
    """
    Add a stylized shiny vignette effect embedded directly on the image.
    Irregular golden glow at edges with sparkle accents.
    """
    import random
    random.seed(42)  # Consistent but "random" look

    result = img.copy()
    w, h = img.width, img.height

    # === LAYER 1: Irregular edge glow (not uniform) ===
    edge_glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(edge_glow)

    # Top edge - varying intensity blobs
    for x in range(0, w, 15):
        intensity = 0.5 + 0.5 * math.sin(x * 0.05)
        blob_h = int(25 + 20 * intensity)
        alpha = int(120 * intensity)
        for y in range(blob_h, 0, -3):
            a = int(alpha * (y / blob_h))
            draw.ellipse([x - 20, -10 - y, x + 20, 10 + y], fill=(255, 180, 60, a))

    # Bottom edge
    for x in range(0, w, 15):
        intensity = 0.5 + 0.5 * math.sin(x * 0.07 + 1)
        blob_h = int(25 + 20 * intensity)
        alpha = int(120 * intensity)
        for y in range(blob_h, 0, -3):
            a = int(alpha * (y / blob_h))
            draw.ellipse([x - 20, h - 10 - y, x + 20, h + 10 + y], fill=(255, 180, 60, a))

    # Left edge
    for y in range(0, h, 15):
        intensity = 0.5 + 0.5 * math.sin(y * 0.06)
        blob_w = int(25 + 20 * intensity)
        alpha = int(120 * intensity)
        for x in range(blob_w, 0, -3):
            a = int(alpha * (x / blob_w))
            draw.ellipse([-10 - x, y - 20, 10 + x, y + 20], fill=(255, 180, 60, a))

    # Right edge
    for y in range(0, h, 15):
        intensity = 0.5 + 0.5 * math.sin(y * 0.08 + 2)
        blob_w = int(25 + 20 * intensity)
        alpha = int(120 * intensity)
        for x in range(blob_w, 0, -3):
            a = int(alpha * (x / blob_w))
            draw.ellipse([w - 10 - x, y - 20, w + 10 + x, y + 20], fill=(255, 180, 60, a))

    edge_glow = edge_glow.filter(ImageFilter.GaussianBlur(radius=12))
    result = Image.alpha_composite(result, edge_glow)

    # === LAYER 2: Corner flares (asymmetric) ===
    corners = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corners)

    corner_data = [
        (0, 0, 1.0),      # Top-left: full
        (w, 0, 0.7),      # Top-right: medium
        (0, h, 0.8),      # Bottom-left: medium-high
        (w, h, 0.6),      # Bottom-right: subtle
    ]

    for corner_x, corner_y, strength in corner_data:
        max_r = int(min(w, h) * 0.3 * strength)
        for r in range(max_r, 0, -3):
            progress = r / max_r
            alpha = int(160 * progress * strength)
            draw.ellipse(
                [corner_x - r, corner_y - r, corner_x + r, corner_y + r],
                fill=(255, 210, 100, alpha)
            )

    corners = corners.filter(ImageFilter.GaussianBlur(radius=15))
    result = Image.alpha_composite(result, corners)

    # === LAYER 3: Sparkle/flare accents scattered near edges ===
    sparkles = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sparkles)

    # Scatter sparkles near edges
    sparkle_positions = [
        # Top edge sparkles
        (w * 0.15, 12), (w * 0.4, 8), (w * 0.7, 15), (w * 0.9, 10),
        # Bottom edge
        (w * 0.1, h - 14), (w * 0.5, h - 10), (w * 0.85, h - 12),
        # Left edge
        (10, h * 0.2), (14, h * 0.6), (8, h * 0.85),
        # Right edge
        (w - 12, h * 0.15), (w - 10, h * 0.5), (w - 15, h * 0.75),
    ]

    for sx, sy in sparkle_positions:
        sx, sy = int(sx), int(sy)
        # Draw 4-point star sparkle
        spark_size = random.randint(8, 16)
        # Horizontal line
        draw.line([(sx - spark_size, sy), (sx + spark_size, sy)],
                  fill=(255, 255, 200, 200), width=2)
        # Vertical line
        draw.line([(sx, sy - spark_size), (sx, sy + spark_size)],
                  fill=(255, 255, 200, 200), width=2)
        # Center glow
        draw.ellipse([sx - 4, sy - 4, sx + 4, sy + 4],
                     fill=(255, 255, 220, 255))

    sparkles = sparkles.filter(ImageFilter.GaussianBlur(radius=3))
    result = Image.alpha_composite(result, sparkles)

    # === LAYER 4: Thin bright edge line (subtle) ===
    edge_line = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(edge_line)

    # Draw thin glowing border just inside the edge
    for offset in [2, 4, 6]:
        alpha = 100 - offset * 12
        draw.rectangle(
            [offset, offset, w - offset - 1, h - offset - 1],
            outline=(255, 220, 150, alpha),
            width=1
        )

    edge_line = edge_line.filter(ImageFilter.GaussianBlur(radius=4))
    result = Image.alpha_composite(result, edge_line)

    return result


async def get_shiny_image(url: str, effect: str = "solar_flare") -> bytes | None:
    """
    Get a shiny version of an image with glowing border.
    Results are cached to avoid re-processing.

    Args:
        url: URL of the original image
        effect: Effect type (currently only "solar_flare")

    Returns:
        PNG image bytes with glow effect, or None on failure
    """
    cache_key = f"{url}_{effect}_v5"  # v5 for stylized edge effect

    if cache_key in _GLOW_CACHE:
        return _GLOW_CACHE[cache_key]

    img = await fetch_image(url)
    if not img:
        log.warning(f"Could not fetch image for shiny effect: {url}")
        return None

    try:
        result = add_solar_flare_explosion(img)

        # Convert to bytes
        buffer = io.BytesIO()
        result.save(buffer, format="PNG", optimize=True)
        image_bytes = buffer.getvalue()

        # Cache the result (with size limit)
        if len(_GLOW_CACHE) >= MAX_CACHE_SIZE:
            oldest = next(iter(_GLOW_CACHE))
            del _GLOW_CACHE[oldest]

        _GLOW_CACHE[cache_key] = image_bytes
        log.info(f"Created shiny glow effect for image ({len(image_bytes)} bytes)")
        return image_bytes

    except Exception as e:
        log.error(f"Failed to apply shiny effect: {e}")
        return None
