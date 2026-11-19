# Church Hub

**Developed by Siamsil Technologies, Inc.**

A private, browser-based app for church members, households, tithes, donations, giving statements, attendance, ministries, events, expenses and **discipleship classes** (Sunday school, Bible study and more). No server, no account, no tracking — records stay in your browser.

## Open the app

1. Extract this folder.
2. Open `index.html` in a modern browser.

For a consistent local address (and offline/installable app support), serve it over HTTP:

    python3 -m http.server 8080

Then open http://localhost:8080. In Chrome/Edge/Safari you can **Install** it as an app.

## What's new in 2.1 — Church Hub and Discipleship

Church Member Manager is now **Church Hub**. The new **Discipleship** section manages learning:

- **Classes & groups:** Sunday school, Bible study, discipleship, youth and adult classes, each with a teacher, schedule, room, age group and capacity.
- **Lessons:** an ordered curriculum per class with Bible passage, memory verse, materials and teacher notes.
- **Rosters:** enroll members from the directory. Full classes add learners to a waitlist, and withdrawing or completing frees a seat for the next person.
- **Sessions & attendance:** record each meeting, the lesson taught and who was present.
- **Progress:** a learner's lesson progress and attendance are calculated from the sessions they attended.
- **Completion:** mark learners completed and print a certificate; print a class roster or export it to CSV.
- **Reports:** sessions, average attendance, lessons taught and completions for every class.
- Deleting a member or class cleans up their learning records. Backups made by earlier versions restore normally.
- Fixed: printing member cards, statements and entries recursed until the browser errored.

## What was new in 2.0 (Siamsil Technologies edition)

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
- `learning.js` — Discipleship (classes, lessons, rosters, sessions)
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
