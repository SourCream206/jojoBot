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
    Overhauled for a 'Powerful Shiny Stand' look.
    Adds high contrast, a bottom-up radiant power aura, glowing embers, 
    and a crisp holographic foil border.
    """
    import random
    from PIL import ImageEnhance, ImageFilter, ImageDraw, Image
    random.seed(42)  # Consistent but dynamic look per rendering

    w, h = img.width, img.height
    
    # === LAYER 1: Base Card Enhancement ===
    # Pop the colors and contrast to make it look "Shiny/Rare"
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.25)
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.4)
    result = img.copy()

    # === LAYER 2: Anime Power Aura ===
    # Rays shooting up from the bottom to simulate raw energy
    aura = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_aura = ImageDraw.Draw(aura)
    
    num_rays = 18
    for _ in range(num_rays):
        # Origin point near the bottom center
        start_x = random.randint(w // 4, (w * 3) // 4)
        start_y = h + 20 
        
        # Destination point spreading outwards toward the top
        end_x = start_x + random.randint(-w // 2, w // 2)
        end_y = random.randint(-50, h // 2)
        
        # Draw an elongated polygon (beam)
        width = random.randint(10, 45)
        alpha = random.randint(20, 70)
        
        draw_aura.polygon([
            (start_x - width // 2, start_y),
            (start_x + width // 2, start_y),
            (end_x + width // 4, end_y),
            (end_x - width // 4, end_y)
        ], fill=(255, 215, 0, alpha)) # Golden aura

    # Blur the rays to make them look like ethereal energy, not geometry
    aura = aura.filter(ImageFilter.GaussianBlur(radius=8))
    result = Image.alpha_composite(result, aura)

    # === LAYER 3: Inner Energy Glow (Vignette) ===
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow)
    
    # Draw concentric rectangles to create a smooth inward gradient
    for i in range(25):
        alpha = int(140 * (1 - (i / 25))**2)  
        draw_glow.rectangle(
            [i, i, w - i - 1, h - i - 1],
            outline=(255, 120, 0, alpha), # Fiery orange deep glow
            width=2
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=4))
    result = Image.alpha_composite(result, glow)

    # === LAYER 4: Floating Embers & Flares ===
    embers = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_embers = ImageDraw.Draw(embers)
    
    for _ in range(35):
        ex = random.randint(0, w)
        ey = random.randint(0, h)
        size = random.randint(1, 4)
        alpha = random.randint(100, 255)
        
        # Core of ember (White/Hot)
        draw_embers.ellipse([ex-size, ey-size, ex+size, ey+size], fill=(255, 255, 255, alpha))
        # Outer glow (Orange/Warm)
        draw_embers.ellipse([ex-size*2, ey-size*2, ex+size*2, ey+size*2], fill=(255, 150, 0, alpha//2))
        
        # Add a classic 4-point anime lens flare to a few random motes
        if random.random() > 0.85:
            flare = size * 5
            draw_embers.line([(ex-flare, ey), (ex+flare, ey)], fill=(255, 255, 200, alpha), width=1)
            draw_embers.line([(ex, ey-flare), (ex, ey+flare)], fill=(255, 255, 200, alpha), width=1)

    embers = embers.filter(ImageFilter.GaussianBlur(radius=1))
    result = Image.alpha_composite(result, embers)

    # === LAYER 5: TCG Foil Border ===
    # Crisp outer edge to frame the card and hold the energy in
    border = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_border = ImageDraw.Draw(border)
    # Outer bright line
    draw_border.rectangle([0, 0, w-1, h-1], outline=(255, 255, 220, 255), width=2)
    # Inner thin line
    draw_border.rectangle([4, 4, w-5, h-5], outline=(255, 200, 0, 180), width=1)
    result = Image.alpha_composite(result, border)

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
