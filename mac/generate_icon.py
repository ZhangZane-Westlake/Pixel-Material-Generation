#!/usr/bin/env python3
"""Generate a simple macOS AppIcon for Pixel Material Generator."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

SIZES: Final[list[int]] = [16, 32, 64, 128, 256, 512, 1024]


def draw_icon(size: int) -> Image.Image:
    """Draw a rounded pixel-art icon.

    Args:
        size: Icon side length in pixels.

    Returns:
        Rendered icon image.
    """
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, size, size], radius=size // 5, fill="#172033")
    tile = max(size // 8, 2)
    colors = ["#43c77b", "#2d8cff", "#f6d365", "#ff6b9a"]
    for index, color in enumerate(colors):
        x = size // 2 - tile * 2 + index * tile
        y = size // 2 - tile // 2 + ((index % 2) * tile)
        draw.rectangle([x, y, x + tile - 1, y + tile - 1], fill=color)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", size // 4)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 4), "APNG", fill="#f4f7fb", anchor="mm", font=font)
    return image


def main() -> None:
    """Generate AppIcon.icns in the mac packaging directory."""
    mac_dir = Path(__file__).resolve().parent
    iconset_path = Path(tempfile.mkdtemp(suffix=".iconset"))
    try:
        for size in SIZES:
            image = draw_icon(size)
            image.save(iconset_path / f"icon_{size}x{size}.png")
            if size <= 512:
                image.resize((size * 2, size * 2), Image.Resampling.NEAREST).save(
                    iconset_path / f"icon_{size}x{size}@2x.png"
                )
        subprocess.run(
            ["iconutil", "-c", "icns", "-o", str(mac_dir / "AppIcon.icns"), str(iconset_path)],
            check=True,
        )
    finally:
        shutil.rmtree(iconset_path, ignore_errors=True)


if __name__ == "__main__":
    main()
