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
    Creates a stylized plasma border effect.
    Acts as a transparent overlay along the edges without covering the center.
    """
    import random
    import math
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

    w, h = img.width, img.height
    result = img.copy().convert("RGBA")

    # === LAYER 1: Base Card Enhancement ===
    # Punch up the contrast to make the Stand pop
    result = ImageEnhance.Contrast(result).enhance(1.15)
    result = ImageEnhance.Color(result).enhance(1.2)

    # === LAYER 2: Transparent Plasma Overlay ===
    # A single transparent layer for the border effect
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    # Scale border thickness dynamically, keeping it thin enough to leave the center clear
    base_t = int(min(w, h) * 0.08) 

    def draw_plasma_edge(draw_obj, edge_type, base_thickness, color, wave_freq):
        steps = 80
        for i in range(steps + 1):
            progress = i / steps
            
            # Create rolling, organic waves combining sin and cos
            wave = math.sin(progress * math.pi * wave_freq) + math.cos(progress * math.pi * wave_freq * 0.5)
            thickness = int(base_thickness + (wave * base_thickness * 0.3))
            
            # Determine coordinates based on edge
            if edge_type == 'top':
                x, y = int(progress * w), 0
            elif edge_type == 'bottom':
                x, y = int(progress * w), h
            elif edge_type == 'left':
                x, y = 0, int(progress * h)
            elif edge_type == 'right':
                x, y = w, int(progress * h)

            # Draw the plasma node
            draw_obj.ellipse([x - thickness, y - thickness, x + thickness, y + thickness], fill=color)

    edges = ['top', 'bottom', 'left', 'right']
    
    for e in edges:
        freq = random.uniform(2.5, 5.0)
        # Deep Orange outer corona
        draw_plasma_edge(draw_overlay, e, base_t, (255, 80, 0, 160), freq)       
        # Bright Yellow/Orange inner plasma (removed the solid white)
        draw_plasma_edge(draw_overlay, e, int(base_t * 0.55), (255, 180, 0, 220), freq) 

    # Smooth the entire overlay to blend it seamlessly
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=10))
    
    # Composite the transparent frame directly over the image
    result = Image.alpha_composite(result, overlay)

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
