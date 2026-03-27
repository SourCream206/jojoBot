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
    Add an INTENSE solar flare explosion effect with:
    - Massive outer glow
    - Light rays bursting outward
    - Vignette overlay bleeding onto the card
    - Corner explosions
    """
    # Much larger padding for dramatic effect
    padding = 60

    new_width = img.width + padding * 2
    new_height = img.height + padding * 2

    # Create result canvas
    result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

    img_x = padding
    img_y = padding

    # === LAYER 1: Massive outer glow haze ===
    outer_glow = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(outer_glow)

    # Draw concentric glowing rectangles
    glow_colors = [
        (60, (255, 50, 0, 40)),      # Deep red outer
        (55, (255, 80, 0, 50)),      # Red-orange
        (50, (255, 120, 0, 60)),     # Orange
        (45, (255, 160, 30, 80)),    # Orange-yellow
        (40, (255, 190, 50, 100)),   # Yellow-orange
        (35, (255, 210, 80, 120)),   # Golden
        (30, (255, 230, 120, 150)),  # Bright gold
        (25, (255, 245, 160, 180)),  # Light gold
        (20, (255, 255, 200, 200)),  # Near white
        (15, (255, 255, 230, 230)),  # White-hot
        (10, (255, 255, 255, 255)),  # Pure white
    ]

    for dist, color in glow_colors:
        draw.rectangle(
            [img_x - dist, img_y - dist,
             img_x + img.width + dist, img_y + img.height + dist],
            fill=color
        )

    # Cut out center
    draw.rectangle(
        [img_x + 5, img_y + 5, img_x + img.width - 5, img_y + img.height - 5],
        fill=(0, 0, 0, 0)
    )

    outer_glow = outer_glow.filter(ImageFilter.GaussianBlur(radius=20))
    result = Image.alpha_composite(result, outer_glow)

    # === LAYER 2: Light rays bursting outward ===
    rays = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rays)

    # Center of the card
    cx = img_x + img.width // 2
    cy = img_y + img.height // 2

    # Draw rays emanating from card edges
    num_rays = 32
    ray_length = 80

    for i in range(num_rays):
        angle = (2 * math.pi * i) / num_rays

        # Start from card edge
        if abs(math.cos(angle)) > abs(math.sin(angle)):
            # Horizontal-ish ray
            start_x = img_x + img.width if math.cos(angle) > 0 else img_x
            start_y = cy + int(math.sin(angle) * img.height / 2)
        else:
            # Vertical-ish ray
            start_x = cx + int(math.cos(angle) * img.width / 2)
            start_y = img_y + img.height if math.sin(angle) > 0 else img_y

        # End point extends outward
        end_x = start_x + int(math.cos(angle) * ray_length)
        end_y = start_y + int(math.sin(angle) * ray_length)

        # Draw ray with gradient (multiple lines getting thinner)
        for width, alpha in [(8, 60), (5, 100), (3, 150), (1, 200)]:
            color = (255, 230, 150, alpha)
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=width)

    rays = rays.filter(ImageFilter.GaussianBlur(radius=6))
    result = Image.alpha_composite(result, rays)

    # === LAYER 3: Corner explosions ===
    corners = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(corners)

    corner_positions = [
        (img_x, img_y, -1, -1),                           # Top-left
        (img_x + img.width, img_y, 1, -1),                # Top-right
        (img_x, img_y + img.height, -1, 1),               # Bottom-left
        (img_x + img.width, img_y + img.height, 1, 1),    # Bottom-right
    ]

    for cx, cy, dx, dy in corner_positions:
        # Draw explosion burst at corner
        for i in range(8):
            angle = math.pi / 4 + (math.pi / 2) * (dx * dy < 0)  # Diagonal outward
            angle += (i - 3.5) * 0.15  # Spread

            length = 50 + (i % 3) * 15
            ex = cx + int(math.cos(angle) * length * dx * (1 if dx * dy > 0 else -1))
            ey = cy + int(math.sin(angle) * length * dy * (1 if dx * dy > 0 else -1))

            # Starburst lines
            draw.line([(cx, cy), (cx + dx * length, cy + dy * length)],
                     fill=(255, 255, 200, 180), width=4)

        # Bright center at corner
        draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill=(255, 255, 220, 200))

    corners = corners.filter(ImageFilter.GaussianBlur(radius=8))
    result = Image.alpha_composite(result, corners)

    # === LAYER 4: Paste original image ===
    result.paste(img, (img_x, img_y), img if img.mode == "RGBA" else None)

    # === LAYER 5: Vignette overlay bleeding onto card ===
    vignette = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)

    # Create inward glowing vignette from edges
    vignette_depth = 40  # How far the glow bleeds inward

    for i in range(vignette_depth):
        # Intensity decreases toward center
        alpha = int(180 * (1 - i / vignette_depth) ** 2)
        color = (255, 200, 50, alpha)

        # Draw shrinking rectangle
        draw.rectangle(
            [i, i, img.width - i - 1, img.height - i - 1],
            outline=color,
            width=2
        )

    # Add bright spots at corners that bleed inward
    corner_glow_size = 60
    for corner_x, corner_y in [(0, 0), (img.width, 0), (0, img.height), (img.width, img.height)]:
        for r in range(corner_glow_size, 0, -3):
            alpha = int(150 * (1 - r / corner_glow_size))
            draw.ellipse(
                [corner_x - r, corner_y - r, corner_x + r, corner_y + r],
                fill=(255, 220, 100, alpha)
            )

    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=10))

    # Composite vignette onto the card area
    result.paste(
        Image.alpha_composite(
            result.crop((img_x, img_y, img_x + img.width, img_y + img.height)),
            vignette
        ),
        (img_x, img_y)
    )

    # === LAYER 6: Bright edge highlight ===
    edge_highlight = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(edge_highlight)

    # Super bright white edge right on the card border
    draw.rectangle(
        [img_x - 3, img_y - 3, img_x + img.width + 3, img_y + img.height + 3],
        outline=(255, 255, 255, 255),
        width=3
    )
    draw.rectangle(
        [img_x - 6, img_y - 6, img_x + img.width + 6, img_y + img.height + 6],
        outline=(255, 240, 150, 200),
        width=3
    )

    edge_highlight = edge_highlight.filter(ImageFilter.GaussianBlur(radius=4))
    result = Image.alpha_composite(result, edge_highlight)

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
    cache_key = f"{url}_{effect}_v2"  # v2 for new effect

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
