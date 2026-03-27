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
    Add a shiny vignette effect embedded directly on the image.
    Golden/fiery glow bleeds inward from edges - no frame, just overlay.
    """
    # Work directly on the image size - no padding
    result = img.copy()
    w, h = img.width, img.height
    cx, cy = w // 2, h // 2

    # === LAYER 1: Radial vignette glow from edges ===
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)

    # Draw elliptical glow from outside inward (larger ellipses = outer edge)
    max_radius = int(math.sqrt(w * w + h * h) / 2)

    # Glow rings from edge bleeding toward center
    for i in range(max_radius, 0, -3):
        # How far from edge (0 = at edge, 1 = at center)
        progress = 1 - (i / max_radius)

        # Only glow in outer ~60% of the image
        if progress > 0.4:
            continue

        # Intensity peaks at edge, fades toward center
        intensity = (0.4 - progress) / 0.4
        alpha = int(180 * intensity ** 1.5)

        # Color shifts from deep orange at edge to golden yellow inward
        r = 255
        g = int(150 + 100 * progress)
        b = int(50 * progress)

        draw.ellipse(
            [cx - i, cy - i, cx + i, cy + i],
            fill=(r, g, b, alpha)
        )

    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=25))
    result = Image.alpha_composite(result, vignette)

    # === LAYER 2: Corner flares (circular, bleeding inward) ===
    corners = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corners)

    corner_positions = [
        (0, 0), (w, 0), (0, h), (w, h)
    ]

    for corner_x, corner_y in corner_positions:
        # Large circular glow at each corner
        max_r = int(min(w, h) * 0.5)
        for r in range(max_r, 0, -4):
            progress = r / max_r
            alpha = int(140 * progress ** 0.8)
            draw.ellipse(
                [corner_x - r, corner_y - r, corner_x + r, corner_y + r],
                fill=(255, 200, 80, alpha)
            )

    corners = corners.filter(ImageFilter.GaussianBlur(radius=20))
    result = Image.alpha_composite(result, corners)

    # === LAYER 3: Soft light rays from corners ===
    rays = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rays)

    for corner_x, corner_y in corner_positions:
        # Direction toward center
        dx = 1 if corner_x == 0 else -1
        dy = 1 if corner_y == 0 else -1

        # Draw several rays from this corner
        for j in range(5):
            angle = math.atan2(cy - corner_y, cx - corner_x) + (j - 2) * 0.25
            ray_len = int(min(w, h) * 0.6)

            end_x = corner_x + int(math.cos(angle) * ray_len)
            end_y = corner_y + int(math.sin(angle) * ray_len)

            for width, alpha in [(10, 30), (6, 50), (3, 70)]:
                draw.line(
                    [(corner_x, corner_y), (end_x, end_y)],
                    fill=(255, 230, 150, alpha),
                    width=width
                )

    rays = rays.filter(ImageFilter.GaussianBlur(radius=15))
    result = Image.alpha_composite(result, rays)

    # === LAYER 4: Enhance brightness/saturation slightly ===
    enhancer = ImageEnhance.Brightness(result)
    result = enhancer.enhance(1.05)

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
    cache_key = f"{url}_{effect}_v4"  # v4 for embedded vignette effect

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
