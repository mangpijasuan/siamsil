# Church Member Manager

**Developed by Siamsil Technologies, Inc.**

A private, browser-based app for church members, households, tithes, donations, giving statements, attendance, ministries, events and expenses. No server, no account, no tracking — records stay in your browser.

## Open the app

1. Extract this folder.
2. Open `index.html` in a modern browser.

For a consistent local address (and offline/installable app support), serve it over HTTP:

    python3 -m http.server 8080

Then open http://localhost:8080. In Chrome/Edge/Safari you can **Install** it as an app.

## What's new in 2.0 (Siamsil Technologies edition)

- Siamsil Technologies, Inc. branding: header byline, footer, About dialog, printed-document credit, app icon.
- Installable offline app (web manifest + service worker; app files only — records never leave the browser).
- Delete members, households, events and expenses with confirmation. Records with giving history are protected so ledgers and statements stay accurate.
- Member directory CSV export.
- Upcoming birthdays (next 30 days) on the home screen.
- Backup reminder when no backup has been downloaded in 30 days.
- Configurable currency (Settings → Church information).
- Automatic dark mode.

## Files

- `index.html` — entry point
- `app.js` — application logic
- `style.css` — layout and theme
- `qr.js` — member QR codes
- `manifest.webmanifest`, `sw.js`, `icon.svg` — installable app support

## Your records

The app starts with fictional sample records. Use **Settings → Start Empty Register** to begin with your own. Download backups regularly (Settings → Download Backup); restore them with Settings → Restore Backup. Backups made with the previous version restore normally.

Shared staff accounts, cloud sync and online payment collection are not included in this version.

Giving statements print via the browser's Save as PDF. Giving ledgers export to CSV.

## Credits & license

© 2026 Siamsil Technologies, Inc. All rights reserved.

QR generation uses QRCode for JavaScript, copyright 2009 Kazuhiko Arase, under the MIT license.
