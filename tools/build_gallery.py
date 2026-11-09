"""Compose gallery images from complete, proportionally scaled browser viewports.

No screenshot cropping, retouching, labels over page content, or fabricated imagery.
Run check_layout.py --screenshots first. Input hashes must match its manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "screenshots"
GALLERY = ROOT / "gallery"
SIZE = (1280, 769)
NAVY, INK, GREEN, WHITE, RED = "#0c1729", "#142239", "#39e4ae", "#f8fbff", "#fa6c74"
DISCLOSURE = "Self-created demo"


def reserve(canvas: Image.Image, box: tuple, label: str) -> None:
    """Prevent labels and screenshot frames from covering one another."""
    occupied = canvas.info.setdefault("layout_boxes", [])
    for previous, previous_label in occupied:
        if min(box[2], previous[2]) > max(box[0], previous[0]) and min(
            box[3], previous[3]
        ) > max(box[1], previous[1]):
            raise ValueError(f"Gallery overlap: {label} / {previous_label}")
    occupied.append((box, label))


def font(size: int, bold: bool = False):
    override = os.getenv("GALLERY_FONT_BOLD" if bold else "GALLERY_FONT_REGULAR")
    candidates = (
        [Path(override)]
        if override
        else [
            Path(os.getenv("WINDIR", "C:/Windows"))
            / "Fonts"
            / ("arialbd.ttf" if bold else "arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu")
            / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
            Path("/System/Library/Fonts/Supplemental")
            / ("Arial Bold.ttf" if bold else "Arial.ttf"),
        ]
    )
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    if override:
        raise FileNotFoundError(f"Configured gallery font is unavailable: {override}")
    return ImageFont.load_default(size=size)


def text(
    canvas: Image.Image,
    xy: tuple[int, int],
    value: str,
    size: int = 22,
    color: str = INK,
    bold: bool = False,
) -> None:
    draw = ImageDraw.Draw(canvas)
    box = draw.textbbox(xy, value, font=font(size, bold))
    if box[0] < 0 or box[2] > SIZE[0] or box[3] > SIZE[1]:
        raise ValueError(f"Gallery label extends outside canvas: {value}")
    reserve(canvas, box, value)
    draw.text(xy, value, font=font(size, bold), fill=color)


def screenshot(
    canvas: Image.Image, source: Image.Image, xy: tuple[int, int], width: int
) -> None:
    height = round(source.height * width / source.width)
    x, y = xy
    if x < 0 or y < 0 or x + width > SIZE[0] or y + height > SIZE[1]:
        raise ValueError("Screenshot extends outside gallery canvas")
    reserve(canvas, (x - 3, y - 3, x + width + 3, y + height + 3), "browser screenshot")
    ImageDraw.Draw(canvas).rectangle(
        (x - 3, y - 3, x + width + 2, y + height + 2), fill="#b7c4d8"
    )
    canvas.paste(source.resize((width, height), Image.Resampling.LANCZOS), xy)


def load_captures() -> dict[str, Image.Image]:
    manifest = json.loads((SCREENSHOTS / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["_sources"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(
                f"Source changed since capture: {name}; rerun browser capture"
            )
    captures = {}
    for device, expected in (("desktop", (1280, 800)), ("mobile", (390, 844))):
        for state in ("before", "after"):
            name = f"{state}_{device}_viewport.png"
            path = SCREENSHOTS / name
            if (
                hashlib.sha256(path.read_bytes()).hexdigest()
                != manifest[name]["sha256"]
            ):
                raise ValueError(
                    f"Screenshot hash mismatch: {name}; rerun browser capture"
                )
            with Image.open(path) as image:
                if image.size != expected:
                    raise ValueError(f"Expected {expected}, got {image.size}: {name}")
                captures[f"{state}_{device}"] = image.convert("RGB")
    return captures


def build() -> None:
    captures = load_captures()
    GALLERY.mkdir(exist_ok=True)
    image = Image.new("RGB", SIZE, NAVY)
    text(image, (54, 45), "STWIFT", 32, GREEN, True)
    text(image, (54, 168), "HTML & CSS", 62, WHITE, True)
    text(image, (54, 248), "LAYOUT FIXES", 64, GREEN, True)

    text(image, (57, 590), "Self-created demo", 30, GREEN, True)

    for state, y, color in (("before", 82, RED), ("after", 424, GREEN)):
        text(
            image,
            (745, y - 32),
            state.upper(),
            20,
            color,
            True,
        )
        screenshot(image, captures[f"{state}_desktop"], (745, y), 490)
    image.save(GALLERY / "01_fiverr_main_cover.png", optimize=True, dpi=(72, 72))

    image = Image.new("RGB", SIZE, "#f3f7fc")
    text(image, (48, 30), "DESKTOP LAYOUT REPAIR", 38, INK, True)
    text(image, (50, 88), DISCLOSURE, 21)
    for state, x, color in (("before", 48, "#b02236"), ("after", 664, "#087654")):
        text(image, (x, 151), state.upper(), 25, color, True)
        screenshot(image, captures[f"{state}_desktop"], (x, 202), 568)
    text(image, (50, 625), "1280 x 800", 24, INK, True)

    image.save(GALLERY / "02_desktop_before_after.png", optimize=True, dpi=(72, 72))

    image = Image.new("RGB", SIZE, "#f3f7fc")
    text(image, (48, 27), "MOBILE RESPONSIVE FIXES", 38, INK, True)
    text(image, (50, 82), DISCLOSURE, 21)
    for state, x, color in (("before", 192, "#b02236"), ("after", 842, "#087654")):
        text(image, (x, 125), state.upper(), 23, color, True)
        screenshot(image, captures[f"{state}_mobile"], (x, 170), 244)
    text(image, (50, 722), "390 x 844", 22, INK, True)

    image.save(GALLERY / "03_mobile_before_after.png", optimize=True, dpi=(72, 72))
    for path in sorted(GALLERY.glob("*.png")):
        with Image.open(path) as output:
            print(f"Built {path.name}: {output.size}")


if __name__ == "__main__":
    build()
