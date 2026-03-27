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
    Add an INTENSE solar flare explosion effect that bleeds outward organically:
    - Radial glow emanating from the image
    - Soft light rays bursting in all directions
    - No hard frame borders - everything fades naturally
    """
    # Large padding for the glow to bleed into
    padding = 80

    new_width = img.width + padding * 2
    new_height = img.height + padding * 2

    # Create result canvas
    result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

    img_x = padding
    img_y = padding
    cx = new_width // 2
    cy = new_height // 2

    # === LAYER 1: Massive radial glow (organic, not rectangular) ===
    outer_glow = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(outer_glow)

    # Draw concentric ellipses for organic radial glow
    max_radius = max(new_width, new_height)
    glow_steps = [
        (1.0, (255, 50, 0, 30)),      # Deep red outer
        (0.9, (255, 80, 0, 45)),      # Red-orange
        (0.8, (255, 120, 0, 60)),     # Orange
        (0.7, (255, 160, 30, 80)),    # Orange-yellow
        (0.6, (255, 190, 50, 100)),   # Yellow-orange
        (0.5, (255, 210, 80, 130)),   # Golden
        (0.4, (255, 230, 120, 160)),  # Bright gold
        (0.3, (255, 245, 160, 190)),  # Light gold
        (0.2, (255, 255, 200, 220)),  # Near white
        (0.15, (255, 255, 230, 240)), # White-hot
    ]

    for scale, color in glow_steps:
        rx = int(max_radius * scale * 0.7)
        ry = int(max_radius * scale * 0.6)
        draw.ellipse(
            [cx - rx, cy - ry, cx + rx, cy + ry],
            fill=color
        )

    outer_glow = outer_glow.filter(ImageFilter.GaussianBlur(radius=35))
    result = Image.alpha_composite(result, outer_glow)

    # === LAYER 2: Light rays bursting outward from center ===
    rays = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rays)

    # Draw rays emanating from center
    num_rays = 48
    ray_length_base = 120

    for i in range(num_rays):
        angle = (2 * math.pi * i) / num_rays
        # Vary ray length for organic feel
        ray_length = ray_length_base + (i % 5) * 15

        # Start from near center
        start_x = cx + int(math.cos(angle) * 30)
        start_y = cy + int(math.sin(angle) * 30)

        # End point extends outward
        end_x = cx + int(math.cos(angle) * ray_length)
        end_y = cy + int(math.sin(angle) * ray_length)

        # Draw ray with gradient (multiple lines getting thinner)
        for width, alpha in [(12, 40), (8, 70), (5, 100), (2, 140)]:
            color = (255, 230, 150, alpha)
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)

    rays = rays.filter(ImageFilter.GaussianBlur(radius=10))
    result = Image.alpha_composite(result, rays)

    # === LAYER 3: Secondary glow pulsing outward ===
    pulse = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pulse)

    # Organic blobs around the edges
    for i in range(16):
        angle = (2 * math.pi * i) / 16
        dist = 60 + (i % 3) * 20
        bx = cx + int(math.cos(angle) * dist)
        by = cy + int(math.sin(angle) * dist)
        blob_size = 40 + (i % 4) * 10

        for r in range(blob_size, 0, -5):
            alpha = int(120 * (r / blob_size))
            draw.ellipse(
                [bx - r, by - r, bx + r, by + r],
                fill=(255, 220, 100, alpha)
            )

    pulse = pulse.filter(ImageFilter.GaussianBlur(radius=15))
    result = Image.alpha_composite(result, pulse)

    # === LAYER 4: Paste original image ===
    result.paste(img, (img_x, img_y), img if img.mode == "RGBA" else None)

    # === LAYER 5: Soft inner glow bleeding onto the image ===
    vignette = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)

    # Radial glow from edges bleeding inward (soft, no hard edges)
    img_cx = img.width // 2
    img_cy = img.height // 2

    # Corner glows that bleed inward organically
    corner_positions = [
        (0, 0), (img.width, 0),
        (0, img.height), (img.width, img.height)
    ]

    for corner_x, corner_y in corner_positions:
        for r in range(80, 0, -4):
            alpha = int(100 * (1 - r / 80) ** 1.5)
            draw.ellipse(
                [corner_x - r, corner_y - r, corner_x + r, corner_y + r],
                fill=(255, 220, 100, alpha)
            )

    # Edge glow bleeding inward
    edge_glow_depth = 30
    for i in range(edge_glow_depth):
        alpha = int(80 * (1 - i / edge_glow_depth) ** 2)
        color = (255, 200, 80, alpha)
        draw.rectangle(
            [i, i, img.width - i - 1, img.height - i - 1],
            outline=color,
            width=3
        )

    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=12))

    # Composite vignette onto the card area
    result.paste(
        Image.alpha_composite(
            result.crop((img_x, img_y, img_x + img.width, img_y + img.height)),
            vignette
        ),
        (img_x, img_y)
    )

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
    cache_key = f"{url}_{effect}_v3"  # v3 for bleeding glow effect

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
