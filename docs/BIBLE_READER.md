# Bible reader

Updated: 2026-10-18 · Route: `/bible`, `/bible/search`

## What it does

- **Read** any version whose display right is cleared (`data/rights.json`). Scripture is fetched and rendered on the server; the toolbar, verse actions and panels are small client components.
- **Bilingual by default.** A Zomi version is paired with English (WEB first, then KJV). `compare=none` turns the second version off.
- **Display modes:** TDB + WEB, TDB only, or WEB only (and equivalent pairings for other available versions). The URL-selected versions determine the actual text; a stale device preference cannot silently hide WEB while the toolbar says TDB + WEB. The settings panel changes the URL and preserves the chapter.
- **Reading settings:** light, sepia or dark (or follow the device), text size 14–24 px, line spacing 1.4–2.1, sans or a Georgia serif. Visual settings are saved in the browser and applied before the first paint by a static inline script in the root layout's <head>, so there is no theme flash. The version selection persists in the URL.
- **Navigation:** book sheet with search (Zomi name, English name or code), a chapter grid with arrow-key movement, previous/next that continue into the neighbouring book and never link to a chapter a version lacks.
- **Verse actions:** select a verse by tap, click, or Enter on its number. Copy includes only the visible scripture and its reference; Share includes a canonical verse URL (native share sheet where available, clipboard fallback otherwise). Bookmark, four highlight colours, and private notes remain device-local.
- **Focus Mode:** hides the global sidebar and mobile bottom navigation while keeping the chapter toolbar and Exit Focus control. It retains the reading position when toggled and stays active while changing chapters in the session.
- **Chapter scroll position:** the thin line below the toolbar follows actual scrolling. It is not a completion or reading-history record.
- **Mobile:** the toolbar keeps book, version, settings, and Focus controls within narrow screens; search and saved references remain in Reading settings. The verse-action sheet sits above the main bottom navigation and respects safe areas.
- **Search** (`/bible/search`): every word or an exact phrase, optional book filter, 20 results per page, matches marked in the text. Results link to the verse in its chapter.

## URLs

`/bible?v=tdb&compare=web&book=1&chapter=1#v3`

| Param | Meaning |
|---|---|
| `v` | Main version id. Unknown ids fall back to the first version. |
| `compare` | Second version id, or `none`. Omitted: the bilingual default above. |
| `book`, `chapter` | Canonical book number (1–66) and a chapter the version has. |
| `#vN` | Scrolls to verse N. |

Links made before this change (`?v=…`, `?v=…&compare=…`, `?testament=new`) still work.

API: `GET /api/v1/bible/versions/{id}/search?q=…&phrase=true&book_id=…&limit=…&offset=…` (q 2–100 characters, limit ≤ 50). Matching is a case-insensitive substring match; LIKE wildcards in the query are treated literally.

## Saved data: this device only

Bookmarks, highlights and notes are stored in the browser (`localStorage` key `siamsil.bible.saved`), keyed by version, book, chapter and verse. The saved-reference panel can filter bookmarks, highlights, and notes. Reading settings use `siamsil.bible.preferences`; Focus Mode uses session storage.

- Nothing is sent to the API, so private notes never reach the server or its logs.
- Not synced between devices. Siamsil has OIDC identity but no saved-items table yet (`docs/ARCHITECTURE.md`, phase "saved items"). When that exists, add owner-scoped endpoints and migrate these keys; until then the UI says "saved in this browser only".
- Notes are plain text (rendered as text, never HTML), trimmed and capped at 4,000 characters.

## Verse alignment

Rows are matched by verse number **and** by verse ranges. TDB prints some verses joined (Genesis 1:17-18 is one verse labelled `17-18`); the English verses 17 and 18 then share that row, each with its own small number. A verse one version truly lacks is shown as "Not in TDB", never filled in.

## Data issues found (for content review, not changed)

Scripture text is displayed exactly as stored. These were noticed while testing and need review against the printed TDB:

- **Psalm 119:2** has no verse in the TDB source; verse 3 follows verse 1. The reader shows "Not in TDB" beside WEB 119:2.

## Not built yet

- **Audio Bible.** No licensed recordings and no validated Zomi speech exist in the project, so there is no play button. Needs recordings with rights (see `docs/AUDIO_CONSENT.md`) before any work.
- **AI study assistant.** Later phase, after the reader is stable. It must retrieve and cite the scripture it uses, keep Bible text separate from generated explanation, present interpretation as interpretation, and never generate Zomi scripture or unreviewed Zomi teaching text.
- Account sync for saved items; reading plans; reading history beyond the "recent" list in the book sheet.

## Tests

```bash
cd frontend
npm test                    # references, alignment, preferences, saved data
npm run lint && npm run typecheck && npm run build
# browser checks against a running app (API on 8001, web on 3002), including 320–1440px and screenshots
SHOTS=./shots node scripts/bible-reader.e2e.mjs     # needs Playwright with Chromium
cd .. && python -m unittest backend.tests.test_bible_versions
```

The V2 browser regression was run on an isolated web preview at port 3102 against the local API on 8001. Screenshots in `docs/screenshots/bible-reader-v2/` are from that actual running UI. No scripture source text or Bible database was modified in V2.
