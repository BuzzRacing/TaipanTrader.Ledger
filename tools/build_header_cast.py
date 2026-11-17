"""Build the SeaTrader admin header: the trading pirate queens around the clipper.

Usage: python build_header_cast.py <web/uploads folder> <output.webp>

Each panel is (file, x0, x1, focus_x, top_y, zoom):
  x0..x1   where the panel sits on the 3200 px canvas
  focus_x  horizontal centre of the crop in the source (0..1)
  top_y    where the crop starts vertically in the source (0..1); portraits start near the head
  zoom     1 = fit the panel width; >1 crops tighter
Neighbouring panels overlap by FEATHER px and are blended softly.
"""
import sys
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
W, H = 3200, 360
FEATHER = 110
BRASS = (201, 163, 78)

PANELS = [
    ("historical-port-hongkong.webp",    0,    1100, 0.40, 0.18, 1.00),  # trading quay - sits behind the wordmark
    ("portrait-agent-0ac6fcf0.png",      1100, 1640, 0.42, 0.04, 1.05),  # harbor agent with her brass scale
    ("historical-ship-clipper.webp",     1640, 2420, 0.40, 0.27, 1.00),  # the clipper
    ("portrait-comprador-923b711d.png",  2420, 2880, 0.50, 0.05, 1.05),  # comprador with abacus among the cargo
    ("portrait-crier-4195e5dd.png",      2880, 3200, 0.40, 0.04, 1.10),  # pirate crier on the quay
]


def crop(path, w, h, fx, ty, zoom):
    im = Image.open(path).convert("RGB")
    sw, sh = im.size
    bw = sw / zoom
    bh = bw * h / w
    if bh > sh:
        bh = sh
        bw = bh * w / h
    x0 = min(max(fx * sw - bw / 2, 0), sw - bw)
    y0 = min(max(ty * sh, 0), sh - bh)
    return im.resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + bw, y0 + bh))


def grade(im):
    im = ImageEnhance.Color(im).enhance(0.93)
    im = ImageEnhance.Contrast(im).enhance(1.05)
    return Image.blend(im, Image.new("RGB", im.size, (60, 38, 20)), 0.06)


def main():
    canvas = Image.new("RGB", (W, H), (21, 16, 12))
    for i, (name, x0, x1, fx, ty, z) in enumerate(PANELS):
        left = x0 - (FEATHER // 2 if i else 0)
        right = min(W, x1 + (FEATHER // 2 if i < len(PANELS) - 1 else 0))
        band = grade(crop(SRC + "/" + name, right - left, H, fx, ty, z))
        mask = Image.new("L", band.size, 255)
        if i:
            md = ImageDraw.Draw(mask)
            for k in range(FEATHER):
                md.line([(k, 0), (k, H)], fill=int(255 * (k / FEATHER) ** 1.2))
        canvas.paste(band, (left, 0), mask)

    # calm top and bottom edges for the brass frame and header text
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    for y in range(H):
        t = y / (H - 1)
        edge = max(0.0, 1 - min(t, 1 - t) / 0.26)
        vd.line([(0, y), (W, y)], fill=int(140 * edge ** 1.6))
    canvas = Image.composite(Image.new("RGB", (W, H), (8, 10, 11)), canvas, vig)

    # brass rules with a diamond at each seam
    d = ImageDraw.Draw(canvas, "RGBA")
    for _, x0, _, _, _, _ in PANELS[1:]:
        for off, a in ((0, 150), (-1, 55), (1, 55)):
            d.line([(x0 + off, 24), (x0 + off, H - 24)], fill=BRASS + (a,), width=1)
        cy, r = H // 2, 9
        d.polygon([(x0, cy - r), (x0 + r, cy), (x0, cy + r), (x0 - r, cy)], fill=(21, 16, 12, 230), outline=BRASS + (220,))
        d.polygon([(x0, cy - 3), (x0 + 3, cy), (x0, cy + 3), (x0 - 3, cy)], fill=BRASS + (255,))

    canvas = canvas.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    canvas.save(OUT, "WEBP", quality=88, method=6)
    canvas.save(OUT.rsplit(".", 1)[0] + "_preview.jpg", quality=85)


if __name__ == "__main__":
    main()
