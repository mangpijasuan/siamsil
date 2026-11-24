# Siamsil Design System v1.0 — final visual audit

Build audited: `main` at 79715ff (PRs #112 and #113) plus the small fixes in this PR. Local production build (`next start`) against the local backend. **Not the live website** — production has not been verified or deployed.

## Screenshots
78 screenshots in `docs/design/screenshots/`, named `{light,dark}-{desktop,tablet,mobile}-{page}.jpg`
(13 pages: home/landing, dictionary, translate, ai, bible, songs, library, learn, workspace, profile, resources, about, help; widths 1440, 820, 390 px).
They replace the earlier set, which showed the previous logo.

## Official logo
- `frontend/public/siamsil-wordmark-white.png` and `siamsil-wordmark-navy.png` are byte-identical to the files supplied by the owner (SHA-256 checked, including the white file as served by the app). They are not edited; transparent padding is hidden with CSS only.
- Gold A with red accent and the TECHNOLOGIES line: white wordmark on the navy shell on every page, in both themes and at all three sizes (logo present and loaded on 78/78 page renders).
- The navy wordmark is shipped but not displayed (navy shell was chosen in both themes).

## Checks (automated, Playwright, 78 page renders)
| Check | Result |
|---|---|
| Horizontal overflow at 1440 / 820 / 390 px | None |
| Decorative background images outside the landing page (incl. ::before/::after) | None |
| Console / page errors | None |
| Controls with no accessible name | None |
| Theme attribute matches the chosen theme | 78/78 |
| Text contrast (WCAG AA), all visible text | Dark: 0 failures. Light: 2 per size, both emoji glyphs (📝 📜) in the Learn hub, not text |
| Typography | Inter (UI) and Playfair Display (headings); no other font renders text |
| Standalone link / button targets | All at least 24×24 CSS px (WCAG 2.2). Fixed in this PR: public nav, "View all / Read Bible / Dictionary →", "About Siamsil →", "← Zomi Library", dictionary search clear (32 px), A–Z rail letters (24 px). Inline links inside sentences are exempt. |
| Dark-mode contrast fix | Home note text (3.84:1) raised to AA |

## Functional checks (Playwright)
PASS: default Light; Dark select applies and persists after reload; theme applied before first paint (set at DOMContentLoaded); System follows the device and updates live when the device changes; Light select; sidebar navigation to Dictionary, Translate, Bible, Library, Learn, Siamsil AI, Resources, About, Help, Workspace; landing "Workspace" button; dictionary returns results for "water"; mobile bottom nav visible; mobile menu opens.

## Tests
- **Unit tests** (`npm test`, Node test runner): 58/58 pass. These cover pure logic (appearance, Bible preferences, etc.), not the UI.
- **Lint, TypeScript, production build:** all pass.
- **End-to-end:** there is no committed end-to-end suite. The browser checks above are ad-hoc audit scripts run once, not part of CI.
- **Not done:** screen-reader testing, real iOS/Android devices, cross-browser (Chromium only), live production.
