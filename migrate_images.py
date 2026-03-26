"""
migrate_images.py
Downloads all stand images from Discord CDN and prepares them for GitHub hosting.

Usage:
1. Run this script: python migrate_images.py
2. Images will be saved to ./images/stands/
3. A new stands_github.json will be created with updated URLs
4. Review and rename stands_github.json to stands.json when ready

After running:
1. git add images/
2. git commit -m "Add stand images"
3. git push
4. Replace stands.json with stands_github.json
"""

import json
import os
import re
import asyncio
import aiohttp
from pathlib import Path

# === CONFIGURATION ===
# Update these with your GitHub info
GITHUB_USERNAME = "SourCream206"  # <-- Change this!
GITHUB_REPO = "jojoBot"                    # <-- Change if different
GITHUB_BRANCH = "main"

# Paths
STANDS_JSON = "stands.json"
OUTPUT_DIR = "images/stands"
OUTPUT_JSON = "stands_github.json"


def sanitize_filename(name: str) -> str:
    """Convert stand name to safe filename."""
    # Replace special chars with underscores
    safe = re.sub(r'[^\w\s-]', '', name)
    safe = re.sub(r'[\s]+', '_', safe)
    return safe.lower()


def get_github_url(filename: str) -> str:
    """Generate GitHub raw URL for a file."""
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/{OUTPUT_DIR}/{filename}"


async def download_image(session: aiohttp.ClientSession, url: str, filepath: Path) -> bool:
    """Download an image from URL to filepath."""
    if not url or not url.startswith("http"):
        return False

    # Skip if already downloaded
    if filepath.exists():
        print(f"  [SKIP] Already exists: {filepath.name}")
        return True

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                content = await resp.read()
                filepath.write_bytes(content)
                print(f"  [OK] Downloaded: {filepath.name}")
                return True
            else:
                print(f"  [FAIL] HTTP {resp.status}: {filepath.name}")
                return False
    except Exception as e:
        print(f"  [ERROR] {filepath.name}: {e}")
        return False


async def process_stand(session: aiohttp.ClientSession, stand_name: str, stand_data: dict) -> dict:
    """Process a single stand - download images and update URLs."""
    new_data = stand_data.copy()
    safe_name = sanitize_filename(stand_name)

    # Process base image
    if "image" in stand_data and stand_data["image"]:
        filename = f"{safe_name}.png"
        filepath = Path(OUTPUT_DIR) / filename
        if await download_image(session, stand_data["image"], filepath):
            new_data["image"] = get_github_url(filename)

    # Process star images
    if "stars" in stand_data:
        new_stars = {}
        for star_level, url in stand_data["stars"].items():
            if url:
                filename = f"{safe_name}_{star_level}.png"
                filepath = Path(OUTPUT_DIR) / filename
                if await download_image(session, url, filepath):
                    new_stars[star_level] = get_github_url(filename)
                else:
                    new_stars[star_level] = url  # Keep original if download failed
            else:
                new_stars[star_level] = url
        new_data["stars"] = new_stars

    return new_data


async def main():
    print("=" * 60)
    print("Stand Image Migration Tool")
    print("=" * 60)

    if GITHUB_USERNAME == "YOUR_GITHUB_USERNAME":
        print("\n[!] Please edit this script and set GITHUB_USERNAME first!")
        print("    Open migrate_images.py and change line 24")
        return

    # Create output directory
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Load stands.json
    print(f"\nLoading {STANDS_JSON}...")
    with open(STANDS_JSON, "r", encoding="utf-8") as f:
        stands_data = json.load(f)

    new_data = {}

    async with aiohttp.ClientSession() as session:
        for part_name, part_stands in stands_data.items():
            print(f"\n--- {part_name} ---")
            new_data[part_name] = {}

            for stand_name, stand_info in part_stands.items():
                print(f"\n{stand_name}:")
                new_data[part_name][stand_name] = await process_stand(
                    session, stand_name, stand_info
                )

    # Save new JSON
    print(f"\n\nSaving {OUTPUT_JSON}...")
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent=4, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print(f"""
Next steps:
1. Check the images in ./{OUTPUT_DIR}/
2. Review {OUTPUT_JSON} to make sure URLs look correct
3. Run these git commands:

   git add images/
   git commit -m "Add stand images for permanent hosting"
   git push

4. After pushing, rename the JSON:

   mv {OUTPUT_JSON} {STANDS_JSON}

   (or on Windows: move {OUTPUT_JSON} {STANDS_JSON})

5. Commit the updated stands.json:

   git add stands.json
   git commit -m "Update image URLs to GitHub raw"
   git push
""")


if __name__ == "__main__":
    asyncio.run(main())
