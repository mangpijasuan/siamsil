# Siamsil logo

Chosen by the project owner on 2026-11-19: the **quill-and-books mark** from the earlier logo, with today's **SIAMSIL** wordmark and **Technology Hub** tagline. The small icon is a simplified flat drawing of the same mark, so it stays clear at 16 pixels.

## Sources (do not edit)

| File | What it is |
|---|---|
| `quill-books-logo-source.png` | The earlier logo, supplied by the owner. Only its quill-and-books mark (left part) is used. |
| `wordmark-source.png` | The SIAMSIL / Technology Hub logo as it was before this change. Only its wordmark (right part) is used. |
| `../../public/siamsil-mark.svg` | The icon: the quill and books drawn flat, on a navy tile. Vector, so it is the master for every icon size. |

The two PNGs are used as they are: cropped and placed, never redrawn. If the original design files (SVG, AI or PDF) turn up, put them here and rebuild from them for sharper print.

## Built files

Run from `frontend/` (needs Pillow; the icon also needs the Playwright Chromium):

```bash
python3 scripts/build-brand.py
```

| File | Use |
|---|---|
| `public/logo-lockup.png` | The lockup in white and gold on a transparent background: the navy top bar, sidebar and menu |
| `public/logo-lockup-light.png` | The same with the white parts in navy: light pages, documents, print |
| `public/logo-og.png` | 1200 x 630 link preview: the lockup on navy |
| `public/logo.png` | 512 px app icon and touch icon |
| `app/favicon.ico` | Browser-tab icon at 16, 32, 48 and 64 px, each rendered from the vector |

Colours: navy `#102746`, gold `#d9b36c`, ivory `#f8f4ea`.
