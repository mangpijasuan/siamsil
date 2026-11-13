#!/usr/bin/env python3
"""Cut the pieces out of the owner's design sheets (design/*.png) into public/theme/.

  python3 frontend/scripts/slice-design-sheet.py

Feature tiles keep their colours (rounded PNG). Sidebar and stat glyphs become white masks, so CSS can colour them
(white on navy, navy on the gold active pill, gold in the stats bar). The pieces are cut at the sheet's own size:
the sheet is a raster, so a clean redraw as SVG would sharpen them on high-density screens.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent.parent
SHEET = Image.open(HERE / "design" / "siamsil-design-sheet.png").convert("RGB")
OUT = HERE / "public" / "theme"
OUT.mkdir(parents=True, exist_ok=True)

# Feature card tiles (x0, y0, x1, y1), reading order: dictionary, translate / bible, library / learn, ai.
TILES = {
    "dictionary": (326, 180, 407, 254), "translate": (439, 180, 520, 254),
    "bible": (326, 296, 407, 370), "library": (439, 296, 520, 370),
    "learn": (326, 414, 407, 489), "ai": (439, 414, 520, 489),
}
# Sidebar glyphs in the sheet's order (x0, y0, x1, y1).
SIDE = {
    "home": (35, 185, 68, 214), "dictionary": (36, 231, 67, 257), "translate": (36, 274, 68, 301),
    "bible": (39, 317, 64, 347), "library": (37, 361, 68, 386), "learn": (35, 402, 68, 429),
    "ai": (36, 444, 67, 473), "resources": (37, 488, 66, 517), "about": (37, 532, 67, 562),
    "help": (37, 579, 67, 608), "profile": (40, 625, 66, 653),
}
STATS = {"book": (1267, 560, 1306, 589), "document": (1371, 555, 1405, 593),
         "people": (1469, 555, 1522, 593), "globe": (1580, 554, 1623, 595)}
SCALE = 4  # supersample for smooth masks


def rounded_tile(box, name):
    x0, y0, x1, y1 = box
    side = min(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    tile = SHEET.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side))
    big = tile.resize((side * SCALE, side * SCALE), Image.LANCZOS)
    mask = Image.new("L", big.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius=int(big.width * 0.26), fill=255)
    out = Image.new("RGBA", big.size)
    out.paste(big, (0, 0), mask)
    out.resize((side * 2, side * 2), Image.LANCZOS).save(OUT / f"tile-{name}.png", optimize=True)


def glyph_mask(box, name, prefix, floor=45, ceil=215):
    x0, y0, x1, y1 = box
    pad = 3
    region = SHEET.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    lum = np.asarray(region).astype(float).max(axis=2)
    alpha = np.clip((lum - floor) / (ceil - floor), 0, 1)
    rgba = np.zeros(lum.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")
    img.resize((img.width * 2, img.height * 2), Image.LANCZOS).save(OUT / f"{prefix}-{name}.png", optimize=True)


def faded(box, name, size, fade=0.45, darken=1.0, rounded=False):
    x0, y0, x1, y1 = box
    art = SHEET.crop(box).resize(size, Image.LANCZOS)
    if darken != 1.0:
        art = Image.eval(art, lambda v: int(v * darken))
    alpha = np.ones((size[1], size[0]))
    ramp = int(size[1] * fade)
    alpha[:ramp] = np.linspace(0, 1, ramp)[:, None]
    out = art.convert("RGBA")
    out.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    out.save(OUT / f"{name}.webp", quality=88, method=6)


for key, box in TILES.items():
    rounded_tile(box, key)
for key, box in SIDE.items():
    glyph_mask(box, key, "nav")
for key, box in STATS.items():
    glyph_mask(box, key, "stat", floor=100, ceil=200)  # the stats bar is lighter than the rail, so a higher floor
# White mist mountains for the foot of the verse panel.
faded((1265, 354, 1531, 471), "mist-mountains", (798, 351), fade=0.5)
# Featured Resources photos, from design/siamsil-resources-sheet.png: square, rounded, without the sheet's white frame.
RES = Image.open(HERE / "design" / "siamsil-resources-sheet.png").convert("RGB")
PHOTOS = {"bible": (907, 209, 1198, 438), "books": (1208, 209, 1486, 438),
          "learn": (907, 450, 1198, 680), "culture": (1208, 450, 1486, 680)}
for key, (x0, y0, x1, y1) in PHOTOS.items():
    inset = 8
    x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    side = min(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    photo = RES.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)).resize((240, 240), Image.LANCZOS)
    mask = Image.new("L", (960, 960), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 959, 959), radius=170, fill=255)
    photo = photo.convert("RGBA")
    photo.putalpha(mask.resize((240, 240), Image.LANCZOS))
    photo.save(OUT / f"photo-{key}.webp", quality=90, method=6)
# The Zongam mountain photo (design/zongam-mountain.jpg) is the background of the side panel.
Image.open(HERE / "design" / "zongam-mountain.jpg").convert("RGB").save(OUT / "rail-zongam.webp", quality=82, method=6)
print("wrote", len(list(OUT.iterdir())), "files to", OUT)
