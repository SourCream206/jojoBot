"""
utils/image_effects.py
Image processing utilities for adding visual effects to stand cards.
"""

import io
import aiohttp
from PIL import Image, ImageFilter, ImageEnhance

# Cache to avoid re-processing the same images
_GLOW_CACHE: dict[str, bytes] = {}
MAX_CACHE_SIZE = 50


async def fetch_image(url: str) -> Image.Image | None:
    """Fetch an image from a URL and return as PIL Image."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def add_shiny_glow(img: Image.Image, glow_color: tuple = (255, 215, 0), glow_size: int = 15) -> Image.Image:
    """
    Add a radiant glowing border effect around the image.

    Args:
        img: PIL Image to add glow to
        glow_color: RGB tuple for glow color (default: gold)
        glow_size: Thickness of the glow effect

    Returns:
        New image with glowing border
    """
    # Create a larger canvas for the glow
    padding = glow_size * 2
    new_size = (img.width + padding, img.height + padding)

    # Create the glow layer
    glow_layer = Image.new("RGBA", new_size, (0, 0, 0, 0))

    # Create a solid color version of the image for the glow
    # We'll use the alpha channel to create the glow shape
    alpha = img.getchannel("A") if img.mode == "RGBA" else Image.new("L", img.size, 255)

    # Create colored glow base
    glow_base = Image.new("RGBA", img.size, (*glow_color, 255))
    glow_base.putalpha(alpha)

    # Paste glow base centered on the larger canvas
    offset = (padding // 2, padding // 2)
    glow_layer.paste(glow_base, offset, glow_base)

    # Apply multiple blur passes for a soft, radiant glow
    for i in range(3):
        blur_radius = glow_size * (3 - i) // 2
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Brighten the glow
    enhancer = ImageEnhance.Brightness(glow_layer)
    glow_layer = enhancer.enhance(1.5)

    # Create final composite
    result = Image.new("RGBA", new_size, (0, 0, 0, 0))
    result.paste(glow_layer, (0, 0))

    # Paste original image on top, centered
    result.paste(img, offset, img)

    return result


def add_rainbow_glow(img: Image.Image, glow_size: int = 12) -> Image.Image:
    """
    Add a multi-colored rainbow glow effect for extra shine.
    """
    padding = glow_size * 3
    new_size = (img.width + padding, img.height + padding)
    offset = (padding // 2, padding // 2)

    # Get alpha channel
    alpha = img.getchannel("A") if img.mode == "RGBA" else Image.new("L", img.size, 255)

    result = Image.new("RGBA", new_size, (0, 0, 0, 0))

    # Layer multiple colored glows
    colors = [
        (255, 100, 100, 180),  # Red
        (255, 200, 100, 180),  # Orange
        (255, 255, 100, 180),  # Yellow
        (100, 255, 150, 180),  # Green
        (100, 200, 255, 180),  # Cyan
        (150, 100, 255, 180),  # Purple
    ]

    for i, color in enumerate(colors):
        layer = Image.new("RGBA", img.size, color)
        layer.putalpha(alpha)

        glow = Image.new("RGBA", new_size, (0, 0, 0, 0))
        # Offset each color slightly for rainbow effect
        layer_offset = (offset[0] + (i - 2) * 2, offset[1] + (i - 2) * 2)
        glow.paste(layer, layer_offset, layer)
        glow = glow.filter(ImageFilter.GaussianBlur(radius=glow_size))

        result = Image.alpha_composite(result, glow)

    # Paste original on top
    result.paste(img, offset, img)

    return result


async def get_shiny_image(url: str, use_rainbow: bool = False) -> bytes | None:
    """
    Get a shiny version of an image with glowing border.
    Results are cached to avoid re-processing.

    Args:
        url: URL of the original image
        use_rainbow: If True, use rainbow glow instead of gold

    Returns:
        PNG image bytes with glow effect, or None on failure
    """
    cache_key = f"{url}_{use_rainbow}"

    if cache_key in _GLOW_CACHE:
        return _GLOW_CACHE[cache_key]

    img = await fetch_image(url)
    if not img:
        return None

    # Apply glow effect
    if use_rainbow:
        result = add_rainbow_glow(img)
    else:
        result = add_shiny_glow(img, glow_color=(255, 223, 0), glow_size=12)

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
    return image_bytes
