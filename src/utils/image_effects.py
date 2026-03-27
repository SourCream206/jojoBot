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
    Creates a stylized, border-esque solar flare effect.
    Wraps the edges with glowing plasma, bright cores, and magnetic loops.
    """
    import random
    import math
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

    w, h = img.width, img.height
    result = img.copy().convert("RGBA")

    # === LAYER 1: Base Card Enhancement ===
    # Punch up the contrast to make the center pop against the bright border
    result = ImageEnhance.Contrast(result).enhance(1.15)
    result = ImageEnhance.Color(result).enhance(1.2)

    # Prepare transparent layers for the frame
    corona = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    loops = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    
    draw_corona = ImageDraw.Draw(corona)
    draw_core = ImageDraw.Draw(core)
    draw_loops = ImageDraw.Draw(loops)

    # Scale the border thickness dynamically based on image size
    base_t = int(min(w, h) * 0.10) 

    # --- Helper to draw stylized plasma waves along an edge ---
    def draw_plasma_edge(draw, edge_type, base_thickness, color, wave_freq):
        steps = 60
        for i in range(steps + 1):
            progress = i / steps
            
            # Create rolling, organic waves combining sin and cos
            wave = math.sin(progress * math.pi * wave_freq) + math.cos(progress * math.pi * wave_freq * 0.5)
            thickness = int(base_thickness + (wave * base_thickness * 0.4))
            
            # Add a tiny bit of random jitter
            thickness += random.randint(-int(base_thickness*0.1), int(base_thickness*0.1))

            # Determine coordinates based on which edge we are drawing
            if edge_type == 'top':
                x, y = int(progress * w), 0
            elif edge_type == 'bottom':
                x, y = int(progress * w), h
            elif edge_type == 'left':
                x, y = 0, int(progress * h)
            elif edge_type == 'right':
                x, y = w, int(progress * h)

            # Draw the glowing orb
            draw.ellipse([x - thickness, y - thickness, x + thickness, y + thickness], fill=color)

    # === LAYER 2 & 3: Plasma Corona & Hot Core ===
    edges = ['top', 'bottom', 'left', 'right']
    
    for e in edges:
        # Randomize the wave frequency per edge so it doesn't look perfectly symmetrical
        freq = random.uniform(2.5, 5.0)
        
        # Deep Orange/Red outer corona
        draw_plasma_edge(draw_corona, e, base_t, (255, 80, 0, 160), freq)       
        # Bright Golden middle layer
        draw_plasma_edge(draw_core, e, base_t * 0.6, (255, 200, 50, 200), freq) 
        # White hot inner edge
        draw_plasma_edge(draw_core, e, base_t * 0.25, (255, 255, 255, 255), freq) 

    # === LAYER 4: Solar Prominences (Magnetic Loops) ===
    # Draw arcs of energy shooting inward from the edges
    for _ in range(12): 
        edge = random.choice(edges)
        start_p = random.uniform(0.1, 0.7)
        end_p = start_p + random.uniform(0.1, 0.25)
        loop_h = random.randint(int(base_t * 1.5), int(base_t * 3))
        
        # Drawing an ellipse partially out of bounds creates a perfect loop/arc inside the image
        if edge == 'top':
            x1, x2 = int(start_p * w), int(end_p * w)
            draw_loops.ellipse([x1, -loop_h, x2, loop_h], outline=(255, 230, 100, 150), width=3)
        elif edge == 'bottom':
            x1, x2 = int(start_p * w), int(end_p * w)
            draw_loops.ellipse([x1, h - loop_h, x2, h + loop_h], outline=(255, 230, 100, 150), width=3)
        elif edge == 'left':
            y1, y2 = int(start_p * h), int(end_p * h)
            draw_loops.ellipse([-loop_h, y1, loop_h, y2], outline=(255, 230, 100, 150), width=3)
        elif edge == 'right':
            y1, y2 = int(start_p * h), int(end_p * h)
            draw_loops.ellipse([w - loop_h, y1, w + loop_h, y2], outline=(255, 230, 100, 150), width=3)

    # === LAYER 5: Blurring and Compositing ===
    # Heavy blur on the outer corona, medium blur on the core, light blur on the loops
    corona = corona.filter(ImageFilter.GaussianBlur(radius=18))
    core = core.filter(ImageFilter.GaussianBlur(radius=6))
    loops = loops.filter(ImageFilter.GaussianBlur(radius=2))
    
    # Merge everything together
    result = Image.alpha_composite(result, corona)
    result = Image.alpha_composite(result, core)
    result = Image.alpha_composite(result, loops)

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
