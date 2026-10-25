"""Render the Ryan_DAM "RD" app-icon set from code — one source of truth for every size.

Design: near-black vertical-gradient rounded tile with white bold-italic "RD"
(Apple-ZCode style, minimal letter mark). Rerun after tweaking constants:

    .venv/Scripts/python.exe scripts/generate-icons.py

Outputs (all committed to git):
    brand/logo-1024.png            master artwork
    build/icon.ico                 electron-builder win icon (exe / shortcuts / taskbar)
    apps/desktop/assets/icon.png   BrowserWindow icon (window / taskbar in dev)
    apps/desktop/assets/drag-icon.png  native startDrag cursor icon
    public/favicon.ico             browser tab icon (vite dev at 5173)
    public/favicon-32.png          browser tab icon, png fallback
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MASTER = 1024
BG_TOP, BG_BOTTOM = (58, 58, 66), (24, 24, 30)
FG = (255, 255, 255)
CORNER = 0.219        # tile corner radius, apple "squircle"-ish proportion
TEXT = "RD"
TEXT_SIZE = 0.42      # font size as a fraction of the canvas
FONT_CANDIDATES = ("arialbi.ttf", "arialbd.ttf", "segoeuib.ttf")


def find_font() -> str:
    import os

    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in FONT_CANDIDATES:
        candidate = fonts_dir / name
        if candidate.exists():
            return str(candidate)
    raise SystemExit(f"No usable bold font found in {fonts_dir}")


def render_master() -> Image.Image:
    img = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    radius = round(MASTER * CORNER)

    mask = Image.new("L", (MASTER, MASTER), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, MASTER - 1, MASTER - 1], radius=radius, fill=255)

    gradient = Image.new("RGBA", (MASTER, MASTER))
    gd = ImageDraw.Draw(gradient)
    for y in range(MASTER):
        t = y / (MASTER - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        gd.line([(0, y), (MASTER, y)], fill=(*color, 255))
    img.paste(gradient, (0, 0), mask)

    font = ImageFont.truetype(find_font(), round(MASTER * TEXT_SIZE))
    draw = ImageDraw.Draw(img)
    box = draw.textbbox((0, 0), TEXT, font=font)
    x = (MASTER - (box[2] - box[0])) / 2 - box[0]
    y = (MASTER - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), TEXT, font=font, fill=FG)
    return img


def main() -> None:
    master = render_master()
    targets = {
        "brand/logo-1024.png": None,
        "build/icon.ico": [16, 24, 32, 48, 64, 128, 256],
        "apps/desktop/assets/icon.png": 512,
        "apps/desktop/assets/drag-icon.png": 64,
        "public/favicon.ico": [16, 32],
        "public/favicon-32.png": 32,
    }
    for rel, sizes in targets.items():
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".ico"):
            master.save(out, format="ICO", sizes=[(s, s) for s in sizes])
        elif sizes is None:
            master.save(out)
        else:
            master.resize((sizes, sizes), Image.LANCZOS).save(out)
        print(f"wrote {rel}")


if __name__ == "__main__":
    main()
