"""
add_stand_image.py
Easily add or update stand images and auto-generate GitHub raw URLs.

Usage:
  python add_stand_image.py                    # Scan and update all missing URLs
  python add_stand_image.py "Star Platinum" 2  # Add specific stand at star level 2
  python add_stand_image.py --push             # Update, commit, and push to GitHub

Workflow:
  1. Put your image in images/stands/ with naming: stand_name_star.png
     Examples: star_platinum_1.png, killer_queen_3.png, the_world_5.png

  2. Run: python add_stand_image.py

  3. The script updates stands.json with the GitHub raw URL

  4. Commit and push when ready (or use --push flag)
"""

import json
import re
import sys
import subprocess
from pathlib import Path

# === CONFIGURATION ===
GITHUB_USERNAME = "SourCream206"
GITHUB_REPO = "jojoBot"
GITHUB_BRANCH = "main"

STANDS_JSON = Path("stands.json")
IMAGES_DIR = Path("images/stands")


def sanitize_filename(name: str) -> str:
    """Convert stand name to filename format."""
    safe = re.sub(r'[^\w\s-]', '', name)
    safe = re.sub(r'[\s]+', '_', safe)
    return safe.lower()


def filename_to_stand_name(filename: str) -> tuple[str, int]:
    """
    Convert filename back to stand name and star level.
    E.g., 'star_platinum_3.png' -> ('Star Platinum', 3)
    """
    # Remove extension and split by underscore
    base = filename.replace('.png', '').replace('.jpg', '').replace('.jpeg', '')

    # Try to extract star level from end
    parts = base.rsplit('_', 1)
    if len(parts) == 2 and parts[1].isdigit():
        name_part = parts[0]
        star = int(parts[1])
    else:
        name_part = base
        star = 1

    # Convert back to title case
    name = name_part.replace('_', ' ').title()
    return name, star


def get_github_url(filename: str) -> str:
    """Generate GitHub raw URL for a file."""
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/{GITHUB_BRANCH}/images/stands/{filename}"


def load_stands() -> dict:
    """Load stands.json."""
    with open(STANDS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_stands(data: dict):
    """Save stands.json."""
    with open(STANDS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def find_stand_in_json(stands_data: dict, stand_name: str) -> tuple[str, str, dict] | None:
    """Find a stand in the JSON structure. Returns (part_name, stand_key, stand_data) or None."""
    stand_lower = stand_name.lower()

    for part_name, part_stands in stands_data.items():
        for stand_key, stand_data in part_stands.items():
            if stand_key.lower() == stand_lower:
                return part_name, stand_key, stand_data

    return None


def scan_and_update():
    """Scan images folder and update stands.json with any missing URLs."""
    if not IMAGES_DIR.exists():
        print(f"Images directory not found: {IMAGES_DIR}")
        return

    stands_data = load_stands()
    updates = []

    # Scan all image files
    for img_path in IMAGES_DIR.glob("*.png"):
        filename = img_path.name
        stand_name, star = filename_to_stand_name(filename)

        # Find in JSON
        result = find_stand_in_json(stands_data, stand_name)
        if not result:
            print(f"[SKIP] No JSON entry for: {stand_name} (from {filename})")
            continue

        part_name, stand_key, stand_data = result
        github_url = get_github_url(filename)

        # Check if URL needs updating
        current_url = stand_data.get("stars", {}).get(str(star), "")

        if current_url != github_url:
            # Update the URL
            if "stars" not in stand_data:
                stands_data[part_name][stand_key]["stars"] = {}

            stands_data[part_name][stand_key]["stars"][str(star)] = github_url

            # Also update base image if star 1
            if star == 1:
                stands_data[part_name][stand_key]["image"] = github_url

            updates.append(f"{stand_key} ★{star}")
            print(f"[UPDATE] {stand_key} ★{star} -> {github_url}")
        else:
            print(f"[OK] {stand_key} ★{star} already up to date")

    if updates:
        save_stands(stands_data)
        print(f"\n✅ Updated {len(updates)} entries in stands.json")
        print("Run 'git add stands.json && git commit -m \"Update stand images\" && git push' to deploy")
    else:
        print("\n✅ All URLs are up to date!")


def add_specific_stand(stand_name: str, star: int):
    """Add/update a specific stand image URL."""
    filename = f"{sanitize_filename(stand_name)}_{star}.png"
    img_path = IMAGES_DIR / filename

    if not img_path.exists():
        print(f"❌ Image not found: {img_path}")
        print(f"   Please add the image file first, then run this script again.")
        return

    stands_data = load_stands()
    result = find_stand_in_json(stands_data, stand_name)

    if not result:
        print(f"❌ Stand '{stand_name}' not found in stands.json")
        print("   Add the stand entry to stands.json first.")
        return

    part_name, stand_key, stand_data = result
    github_url = get_github_url(filename)

    if "stars" not in stands_data[part_name][stand_key]:
        stands_data[part_name][stand_key]["stars"] = {}

    stands_data[part_name][stand_key]["stars"][str(star)] = github_url

    if star == 1:
        stands_data[part_name][stand_key]["image"] = github_url

    save_stands(stands_data)
    print(f"✅ Updated {stand_key} ★{star}")
    print(f"   URL: {github_url}")


def git_push():
    """Commit and push changes."""
    try:
        subprocess.run(["git", "add", "images/stands/", "stands.json"], check=True)
        subprocess.run(["git", "commit", "-m", "Update stand images"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Pushed to GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")


def main():
    args = sys.argv[1:]

    if "--push" in args:
        args.remove("--push")
        scan_and_update()
        git_push()
    elif len(args) == 0:
        # Scan and update all
        scan_and_update()
    elif len(args) == 2:
        # Add specific stand
        stand_name = args[0]
        star = int(args[1])
        add_specific_stand(stand_name, star)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
