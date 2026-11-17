"""Build the SeaTrader admin header triptych: Trade | Voyage | Danger.

Sources are the canon graphics-bible plates in web/uploads.
Output is sized for the 164 px sticky header at 2x density.
"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

SRC = sys.argv[1]
OUT = sys.argv[2]

W, H = 3200, 360            # ~8.9:1, matches a 1440-1920 px wide, 164 px tall header at 2x
PANEL = W // 3
FEATHER = 150                # soft blend between scenes

# (file, vertical centre of the crop 0..1, horizontal centre 0..1, zoom >= 1)
SCENES = [
    ("historical-port-hongkong.webp", 0.52, 0.55, 1.00),   # TRADE  - quayside market
    ("historical-ship-clipper.webp",  0.54, 0.44, 1.00),   # VOYAGE - clipper under sail
    ("historical-ship-junk.webp",     0.44, 0.52, 1.00),   # DANGER - oxblood-sailed junk at sunset
]

BRASS = (201, 163, 78)


def crop_band(path, cy, cx, zoom, w, h):
    im = Image.open(path).convert("RGB")
    target = w / h
    sw, sh = im.size
    # largest box of the target ratio, then zoom in
    bw = sw / zoom
    bh = bw / target
    if bh > sh / zoom:
        bh = sh / zoom
        bw = bh * target
    x0 = min(max(cx * sw - bw / 2, 0), sw - bw)
    y0 = min(max(cy * sh - bh / 2, 0), sh - bh)
    return im.resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + bw, y0 + bh))


def grade(im):
    # unify the three plates: a touch less saturation, warm lift, gentle contrast
    im = ImageEnhance.Color(im).enhance(0.92)
    im = ImageEnhance.Contrast(im).enhance(1.06)
    warm = Image.new("RGB", im.size, (60, 38, 20))
    return Image.blend(im, warm, 0.06)


def main():
    canvas = Image.new("RGB", (W, H), (21, 16, 12))
    pw = PANEL + FEATHER  # each panel overlaps its neighbour
    for i, (name, cy, cx, z) in enumerate(SCENES):
        band = grade(crop_band(SRC + "/" + name, cy, cx, z, pw, H))
        x = i * PANEL - (FEATHER // 2 if i else 0)
        if i == 0:
            canvas.paste(band, (0, 0))
            continue
        mask = Image.new("L", (pw, H), 255)
        md = ImageDraw.Draw(mask)
        for k in range(FEATHER):
            md.line([(k, 0), (k, H)], fill=int(255 * (k / FEATHER) ** 1.2))
        canvas.paste(band, (x, 0), mask)

    # top/bottom vignette so the brass frame and text sit on calm edges
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    for y in range(H):
        t = y / (H - 1)
        edge = max(0.0, 1 - min(t, 1 - t) / 0.28)
        vd.line([(0, y), (W, y)], fill=int(150 * edge ** 1.6))
    canvas = Image.composite(Image.new("RGB", (W, H), (8, 10, 11)), canvas, vig)

    # brass dividers with a small diamond, echoing the admin ornament
    d = ImageDraw.Draw(canvas, "RGBA")
    for i in (1, 2):
        x = i * PANEL
        for off, a in ((0, 150), (-1, 60), (1, 60)):
            d.line([(x + off, 26), (x + off, H - 26)], fill=BRASS + (a,), width=1)
        cy = H // 2
        r = 9
        d.polygon([(x, cy - r), (x + r, cy), (x, cy + r), (x - r, cy)], fill=(21, 16, 12, 230), outline=BRASS + (220,))
        d.polygon([(x, cy - 3), (x + 3, cy), (x, cy + 3), (x - 3, cy)], fill=BRASS + (255,))

    canvas = canvas.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    canvas.save(OUT, "WEBP", quality=88, method=6)
    canvas.save(OUT.rsplit(".", 1)[0] + "_preview.jpg", quality=85)


if __name__ == "__main__":
    main()
