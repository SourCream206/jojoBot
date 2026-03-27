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
    Creates an even, symmetrical solar star shiny border.
    Uses smooth gradients and geometric star flares instead of uneven fire.
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

    w, h = img.width, img.height
    result = img.copy().convert("RGBA")

    # === LAYER 1: Base Card Enhancement ===
    # Punch up the contrast to make the Stand pop
    result = ImageEnhance.Contrast(result).enhance(1.15)
    result = ImageEnhance.Color(result).enhance(1.2)

    # === LAYER 2: Even, Smooth Solar Glow (Transparent Overlay) ===
    # This creates a perfectly uniform, glowing inner border
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow_layer)

    glow_thickness = int(min(w, h) * 0.12)
    
    for i in range(glow_thickness):
        # Smooth exponential falloff for the glow opacity
        progress = i / glow_thickness
        alpha = int(220 * (1 - progress)**1.5)
        
        # Color transition: deep golden-orange at the very edge to bright pale yellow inside
        r = 255
        g = int(160 + 95 * progress)
        b = int(50 + 150 * progress)
        
        # Draw concentric rectangles moving inward
        draw_glow.rectangle(
            [i, i, w - i - 1, h - i - 1],
            outline=(r, g, b, alpha),
            width=1
        )
        
    # Blur the concentric rectangles so they form a smooth, seamless band of light
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))

    # === LAYER 3: Solar Star Flares ===
    # Adds crisp, even starbursts at the corners and midpoints
    flare_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_flare = ImageDraw.Draw(flare_layer)

    def draw_star(cx, cy, radius, alpha_center, color):
        """Draws a sharp, 4-point optical star flare."""
        # Bright center core
        draw_flare.ellipse(
            [cx - radius//5, cy - radius//5, cx + radius//5, cy + radius//5], 
            fill=(255, 255, 255, alpha_center)
        )
        # Horizontal beam
        draw_flare.polygon([
            (cx - radius, cy), (cx, cy - radius//10), 
            (cx + radius, cy), (cx, cy + radius//10)
        ], fill=color)
        # Vertical beam
        draw_flare.polygon([
            (cx, cy - radius), (cx - radius//10, cy), 
            (cx, cy + radius), (cx + radius//10, cy)
        ], fill=color)

    # Dynamically scale the stars based on the image size
    inset = int(glow_thickness * 0.3)
    flare_size_corner = int(min(w, h) * 0.18)
    flare_size_mid = int(min(w, h) * 0.12)
    flare_color = (255, 240, 150, 200) # Bright pale gold

    # Place large stars near the 4 corners
    corners = [(inset, inset), (w - inset, inset), (inset, h - inset), (w - inset, h - inset)]
    for cx, cy in corners:
        draw_star(cx, cy, flare_size_corner, 255, flare_color)

    # Place slightly smaller stars at the exact midpoints of the 4 edges
    midpoints = [(w//2, inset), (w//2, h - inset), (inset, h//2), (w - inset, h//2)]
    for cx, cy in midpoints:
        draw_star(cx, cy, flare_size_mid, 200, flare_color)

    # A very light blur to make the stars look like glowing light rather than solid polygons
    flare_layer = flare_layer.filter(ImageFilter.GaussianBlur(radius=2))

    # === LAYER 4: Compositing ===
    # Stack the transparent glow and the transparent flares over the original image
    result = Image.alpha_composite(result, glow_layer)
    result = Image.alpha_composite(result, flare_layer)

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
