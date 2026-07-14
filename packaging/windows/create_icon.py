"""Create deterministic Windows and UI icons for the workbench."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
PNG_PATH = ROOT / "material_ai_workbench" / "resources" / "app_icon.png"
ICO_PATH = ROOT / "packaging" / "windows" / "materialai.ico"


def create_icon() -> None:
    size = 512
    image = Image.new("RGBA", (size, size), "#f4f6f8")
    draw = ImageDraw.Draw(image)

    plate = (72, 72, 440, 440)
    draw.rounded_rectangle(plate, radius=22, fill="#dce5eb", outline="#25313c", width=18)

    for coordinate in range(118, 430, 52):
        draw.line((coordinate, 86, coordinate, 426), fill="#8fa2af", width=5)
        draw.line((86, coordinate, 426, coordinate), fill="#8fa2af", width=5)

    hole = (166, 166, 346, 346)
    draw.ellipse(hole, fill="#f4f6f8", outline="#25313c", width=18)
    draw.arc((148, 148, 364, 364), start=210, end=332, fill="#d84a3a", width=16)
    draw.arc((148, 148, 364, 364), start=30, end=152, fill="#2776b9", width=16)

    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(PNG_PATH, format="PNG", optimize=True)
    image.save(
        ICO_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    create_icon()
