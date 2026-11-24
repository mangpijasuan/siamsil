# Siamsil Design System v1.0

Final layer: `frontend/app/siamsil-design.css` (tokens and light/dark overrides). Appearance (Light, Dark, System) is
`frontend/lib/appearance.ts` + `components/AppearanceSelect.tsx`; the choice is applied before first paint and the Bible
reader's "System" theme follows it.

- Palette: French navy `#123a6b`, midnight navy `#051b3b`, white, gold `#e5b522`, logo red `#e00000` (accent only). No purple.
- Decorative artwork only on the public landing page (`/`); the app shell, tool headers, library, Bible reader are flat.
- Logo: the existing repository wordmark (`/logo-lockup.png`) is used unmodified. No new owner logo assets were supplied.
- Screenshots: `docs/design/screenshots/{light,dark}-{desktop,tablet,mobile}-<page>.jpg` (13 pages x 3 sizes x 2 themes).
- Automated contrast audit (WCAG AA, text nodes), 1 residual in dark and 2 in light per page set (a disabled-state button and emoji glyphs); no horizontal overflow at 1440, 820 or 390 px.
