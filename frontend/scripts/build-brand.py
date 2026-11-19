#!/usr/bin/env python3
"""Build the Siamsil logo files from the sources in design/brand/ (see design/brand/README.md).

  python3 scripts/build-brand.py            # from frontend/; needs Pillow

Writes, in public/ and app/:
  logo-lockup.png        quill-and-books mark + SIAMSIL / Technology Hub wordmark, white and gold, transparent (navy bars)
  logo-lockup-light.png  the same with the white parts in navy, for light backgrounds and print
  logo-og.png            1200 x 630 link preview: the lockup on navy
  logo.png               512 px app icon, from public/siamsil-mark.svg
  app/favicon.ico        16, 32, 48 and 64 px, from public/siamsil-mark.svg

The two PNG sources are used as they are: nothing is redrawn, only cropped, placed and (for the light version)
recoloured. The icon is the vector public/siamsil-mark.svg, rendered with the Playwright Chromium if it is
installed; without it the icon files are left unchanged and the script says so.
"""
from __future__ import annotations

import colorsys
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

FRONTEND = Path(__file__).resolve().parents[1]
BRAND = FRONTEND / "design" / "brand"
PUBLIC = FRONTEND / "public"
NAVY = (16, 39, 70)
# Where the quill mark and the wordmark sit in their source files (pixels, left edge to right edge).
MARK_COLUMNS = (0, 345)  # quill-books-logo-source.png: the mark, left of its own wordmark
WORD_COLUMNS = (360, 1200)  # wordmark-source.png: SIAMSIL and Technology Hub, right of the old four-tile mark


def trimmed(image: Image.Image, columns: tuple[int, int]) -> Image.Image:
    part = image.crop((columns[0], 0, columns[1], image.height))
    return part.crop(part.getbbox())


def lockup(mark: Image.Image, word: Image.Image) -> Image.Image:
    """Mark on the left, wordmark centred beside it. The mark stands 1.25 times the wordmark's height."""
    word_height = 272
    word = word.resize((round(word.width * word_height / word.height), word_height), Image.LANCZOS)
    mark_height = round(word_height * 1.25)
    mark = mark.resize((round(mark.width * mark_height / mark.height), mark_height), Image.LANCZOS)
    gap = 36
    canvas = Image.new("RGBA", (mark.width + gap + word.width, mark_height), (0, 0, 0, 0))
    canvas.alpha_composite(mark, (0, 0))
    canvas.alpha_composite(word, (mark.width + gap, (mark_height - word_height) // 2))
    return canvas


def on_light(image: Image.Image) -> Image.Image:
    """White and silver parts become navy; gold and transparency stay as they are."""
    out = image.copy()
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            _, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if saturation < 0.25 or lightness > 0.85:
                pixels[x, y] = (*NAVY, a)
    return out


def link_preview(lock: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (1200, 630), (*NAVY, 255))
    logo = lock.copy()
    logo.thumbnail((960, 330), Image.LANCZOS)
    canvas.alpha_composite(logo, ((1200 - logo.width) // 2, (630 - logo.height) // 2))
    return canvas.convert("RGB")


def render_icon(size: int) -> Image.Image | None:
    """public/siamsil-mark.svg at `size` pixels, through Playwright's Chromium (None if it is not available)."""
    node = shutil.which("node")
    if not node:
        return None
    svg = (PUBLIC / "siamsil-mark.svg").read_text(encoding="utf-8")
    script = (
        "const { chromium } = require('playwright');"
        "(async () => { const b = await chromium.launch();"
        f"const p = await b.newPage({{ viewport: {{ width: {size}, height: {size} }} }});"
        f"await p.setContent(`<style>html,body{{margin:0;background:transparent}}svg{{display:block;width:{size}px;height:{size}px}}</style>${{process.argv[1]}}`);"
        "process.stdout.write(await p.screenshot({ omitBackground: true }));"
        "await b.close(); })().catch(() => process.exit(1));"
    )
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    env = {**os.environ, "NODE_PATH": os.pathsep.join(filter(None, [root, os.environ.get("NODE_PATH", "")]))}
    result = subprocess.run([node, "-e", script, svg], capture_output=True, env=env)
    if result.returncode != 0 or not result.stdout:
        return None
    return Image.open(io.BytesIO(result.stdout)).convert("RGBA")


def main() -> int:
    mark = trimmed(Image.open(BRAND / "quill-books-logo-source.png").convert("RGBA"), MARK_COLUMNS)
    word = trimmed(Image.open(BRAND / "wordmark-source.png").convert("RGBA"), WORD_COLUMNS)
    dark = lockup(mark, word)
    dark.save(PUBLIC / "logo-lockup.png", optimize=True)
    on_light(dark).save(PUBLIC / "logo-lockup-light.png", optimize=True)
    link_preview(dark).save(PUBLIC / "logo-og.png", optimize=True)
    print(f"logo-lockup.png and logo-lockup-light.png: {dark.width} x {dark.height}; logo-og.png: 1200 x 630")

    icon = render_icon(512)
    if icon is None:
        print("Playwright Chromium not found: logo.png and favicon.ico were left unchanged", file=sys.stderr)
        return 0
    icon.save(PUBLIC / "logo.png", optimize=True)
    with tempfile.TemporaryDirectory() as tmp:
        # Each favicon size is rendered from the vector, not shrunk from the 512 px image, so small sizes stay crisp.
        sizes = [16, 32, 48, 64]
        frames = [render_icon(n) or icon.resize((n, n), Image.LANCZOS) for n in sizes]
        frames[-1].save(Path(tmp) / "favicon.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
        shutil.copy(Path(tmp) / "favicon.ico", FRONTEND / "app" / "favicon.ico")
    print("logo.png: 512 x 512; favicon.ico: 16, 32, 48, 64")
    return 0


if __name__ == "__main__":
    sys.exit(main())
