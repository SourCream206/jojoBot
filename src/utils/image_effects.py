"""
utils/image_effects.py
Image processing utilities for adding visual effects to stand cards.
"""

import io
import logging
import aiohttp
from PIL import Image, ImageFilter, ImageDraw

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


def add_solar_flare_glow(img: Image.Image) -> Image.Image:
    """
    Add an intense solar flare glow effect around the image border.
    Creates multiple layers of bright, expanding glow for a dramatic effect.
    """
    # Glow parameters - make it VERY visible
    glow_thickness = 40  # How far the glow extends
    padding = glow_thickness + 10

    new_width = img.width + padding * 2
    new_height = img.height + padding * 2

    # Create the result canvas with transparent background
    result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

    # Position for the original image (centered)
    img_x = padding
    img_y = padding

    # Create multiple glow layers from outer (dimmer) to inner (brighter)
    # This creates the "solar flare" expanding effect
    glow_layers = [
        # (distance from edge, color with alpha, blur amount)
        (40, (255, 100, 0, 60), 25),    # Outer red/orange haze
        (35, (255, 150, 0, 80), 20),    # Orange mid-outer
        (30, (255, 180, 0, 100), 18),   # Orange-yellow
        (25, (255, 200, 0, 130), 15),   # Yellow outer
        (20, (255, 220, 50, 160), 12),  # Bright yellow
        (15, (255, 235, 100, 190), 10), # Intense yellow
        (10, (255, 245, 150, 220), 8),  # Near-white yellow
        (5, (255, 255, 200, 250), 5),   # White-hot inner
        (2, (255, 255, 255, 255), 3),   # Pure white edge
    ]

    for distance, color, blur in glow_layers:
        # Create a layer for this glow ring
        layer = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        # Draw a rectangle slightly larger than the image
        x1 = img_x - distance
        y1 = img_y - distance
        x2 = img_x + img.width + distance
        y2 = img_y + img.height + distance

        # Draw the glow border (filled rectangle, then we'll cut out the middle)
        draw.rectangle([x1, y1, x2, y2], fill=color)

        # Cut out the center to leave just the border
        inner_margin = max(0, distance - 8)
        draw.rectangle(
            [img_x - inner_margin, img_y - inner_margin,
             img_x + img.width + inner_margin, img_y + img.height + inner_margin],
            fill=(0, 0, 0, 0)
        )

        # Apply blur for the glow effect
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))

        # Composite onto result
        result = Image.alpha_composite(result, layer)

    # Add some "flare spikes" at corners for extra effect
    result = _add_corner_flares(result, img_x, img_y, img.width, img.height)

    # Paste the original image on top
    result.paste(img, (img_x, img_y), img if img.mode == "RGBA" else None)

    return result


def _add_corner_flares(img: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    """Add diagonal flare spikes at corners for extra dramatic effect."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Corner positions
    corners = [
        (x, y),                    # Top-left
        (x + w, y),                # Top-right
        (x, y + h),                # Bottom-left
        (x + w, y + h),            # Bottom-right
    ]

    flare_length = 30
    flare_color = (255, 220, 100, 150)

    for cx, cy in corners:
        # Draw small diagonal lines emanating from corners
        for angle_offset in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            ex = cx + angle_offset[0] * flare_length
            ey = cy + angle_offset[1] * flare_length
            draw.line([(cx, cy), (ex, ey)], fill=flare_color, width=3)

    layer = layer.filter(ImageFilter.GaussianBlur(radius=4))
    return Image.alpha_composite(img, layer)


def add_shiny_border_frame(img: Image.Image) -> Image.Image:
    """
    Add a thick glowing golden border frame around the image.
    Simpler but still visually striking.
    """
    border_size = 8
    glow_size = 25
    total_padding = border_size + glow_size

    new_width = img.width + total_padding * 2
    new_height = img.height + total_padding * 2

    result = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

    # Create outer glow
    glow_layer = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow_layer)

    # Draw golden rectangle for glow base
    draw.rectangle(
        [glow_size - 5, glow_size - 5,
         new_width - glow_size + 5, new_height - glow_size + 5],
        fill=(255, 215, 0, 255)
    )
    # Cut out center
    draw.rectangle(
        [total_padding - 2, total_padding - 2,
         total_padding + img.width + 2, total_padding + img.height + 2],
        fill=(0, 0, 0, 0)
    )

    # Blur for glow effect
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=15))
    result = Image.alpha_composite(result, glow_layer)

    # Add solid golden border
    border_layer = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(border_layer)
    draw.rectangle(
        [total_padding - border_size, total_padding - border_size,
         total_padding + img.width + border_size, total_padding + img.height + border_size],
        fill=(255, 200, 50, 255)
    )
    draw.rectangle(
        [total_padding, total_padding,
         total_padding + img.width, total_padding + img.height],
        fill=(0, 0, 0, 0)
    )
    result = Image.alpha_composite(result, border_layer)

    # Paste original image
    result.paste(img, (total_padding, total_padding), img if img.mode == "RGBA" else None)

    return result


async def get_shiny_image(url: str, effect: str = "solar_flare") -> bytes | None:
    """
    Get a shiny version of an image with glowing border.
    Results are cached to avoid re-processing.

    Args:
        url: URL of the original image
        effect: "solar_flare" for intense effect, "border" for simpler frame

    Returns:
        PNG image bytes with glow effect, or None on failure
    """
    cache_key = f"{url}_{effect}"

    if cache_key in _GLOW_CACHE:
        return _GLOW_CACHE[cache_key]

    img = await fetch_image(url)
    if not img:
        log.warning(f"Could not fetch image for shiny effect: {url}")
        return None

    try:
        # Apply glow effect
        if effect == "border":
            result = add_shiny_border_frame(img)
        else:
            result = add_solar_flare_glow(img)

        # Convert to bytes
        buffer = io.BytesIO()
        result.save(buffer, format="PNG", optimize=True)
        image_bytes = buffer.getvalue()

        # Cache the result (with size limit)
        if len(_GLOW_CACHE) >= MAX_CACHE_SIZE:
            # Remove oldest entry
            oldest = next(iter(_GLOW_CACHE))
            del _GLOW_CACHE[oldest]

        _GLOW_CACHE[cache_key] = image_bytes
        log.info(f"Created shiny glow effect for image ({len(image_bytes)} bytes)")
        return image_bytes

    except Exception as e:
        log.error(f"Failed to apply shiny effect: {e}")
        return None
