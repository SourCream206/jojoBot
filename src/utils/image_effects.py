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
    Creates an even, symmetrical solar shiny border with dynamic radial action lines.
    Leaves the center perfectly clear to showcase the Stand.
    """
    import math
    import random
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

    w, h = img.width, img.height
    result = img.copy().convert("RGBA")

    # === LAYER 1: Base Card Enhancement ===
    # Punch up the contrast to make the Stand pop
    result = ImageEnhance.Contrast(result).enhance(1.15)
    result = ImageEnhance.Color(result).enhance(1.2)

    # === LAYER 2: Radial Action Lines ===
    # Manga-style speed/focus lines that radiate outward
    lines_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_lines = ImageDraw.Draw(lines_layer)

    cx, cy = w // 2, h // 2
    max_r = math.hypot(cx, cy)
    # This determines how large the empty center is (30% of the image size)
    min_r = min(w, h) * 0.30 

    num_lines = 65
    for i in range(num_lines):
        # Base angle with a tiny bit of random jitter
        angle_deg = i * (360 / num_lines) + random.uniform(-1.5, 1.5)
        angle = math.radians(angle_deg)
        
        # Vary the thickness of the lines dynamically
        width_angle = math.radians(random.uniform(0.5, 2.5))
        
        # Vary opacity so some rays are bright and others are subtle
        alpha = random.randint(30, 150)
        
        # Inner points of the wedge (narrower, starting outside the center)
        x1 = cx + min_r * math.cos(angle - width_angle/4)
        y1 = cy + min_r * math.sin(angle - width_angle/4)
        x2 = cx + min_r * math.cos(angle + width_angle/4)
        y2 = cy + min_r * math.sin(angle + width_angle/4)
        
        # Outer points of the wedge (wider, reaching the edges)
        x3 = cx + max_r * math.cos(angle + width_angle)
        y3 = cy + max_r * math.sin(angle + width_angle)
        x4 = cx + max_r * math.cos(angle - width_angle)
        y4 = cy + max_r * math.sin(angle - width_angle)

        # Draw the ray using a pale golden-white color
        draw_lines.polygon(
            [(x1, y1), (x2, y2), (x3, y3), (x4, y4)], 
            fill=(255, 245, 180, alpha) 
        )

    # A very light blur to soften the harsh vector edges of the rays
    lines_layer = lines_layer.filter(ImageFilter.GaussianBlur(radius=1))

    # === LAYER 3: Even, Smooth Solar Glow (Transparent Overlay) ===
    # This creates a perfectly uniform, glowing inner border over the lines
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
        
        draw_glow.rectangle(
            [i, i, w - i - 1, h - i - 1],
            outline=(r, g, b, alpha),
            width=1
        )
        
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))

    # === COMPOSITING ===
    # Stack the lines and the glow over the original image
    result = Image.alpha_composite(result, lines_layer)
    result = Image.alpha_composite(result, glow_layer)

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
