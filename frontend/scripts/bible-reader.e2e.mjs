// Browser checks for the Bible reader against a running app.
//   BASE=http://127.0.0.1:3002 API=http://127.0.0.1:8001 SHOTS=./shots node scripts/bible-reader.e2e.mjs
// Needs Playwright with Chromium (e.g. `npx -y -p playwright@1 node scripts/bible-reader.e2e.mjs`).
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

// require() also finds a globally installed Playwright (NODE_PATH), which ESM import does not.
const { chromium } = createRequire(import.meta.url)("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:3002";
const API = process.env.API ?? "http://127.0.0.1:8001";
const SHOTS = process.env.SHOTS ?? "";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

let failures = 0;
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures += 1;
};
const api = async (path) => (await fetch(`${API}/api/v1${path}`)).json();
const shot = async (page, name, fullPage = false) => SHOTS && page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage });

const browser = await chromium.launch({ ...(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {}), args: ["--no-sandbox"] });
const errors = [];
const newPage = async (width, height = 900) => {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: width < 800 ? 2 : 1 });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  return page;
};

// 1. Verse text and alignment match the API exactly (TDB + WEB, Genesis 1).
const tdb = await api("/bible/versions/tdb/chapter?book_id=1&chapter=1");
const web = await api("/bible/versions/web/chapter?book_id=1&chapter=1");
let page = await newPage(1440);
await page.goto(`${BASE}/bible?v=tdb&book=1&chapter=1`, { waitUntil: "networkidle" });
const rows = await page.$$eval(".sb-verse", (items) => items.map((li) => ({
  id: li.id,
  primary: li.querySelector(".sb-primary")?.textContent ?? "",
  secondary: li.querySelector(".sb-secondary")?.textContent ?? "",
})));
check("bilingual by default (TDB with WEB)", rows.length > 0 && rows.every((row) => row.secondary));
const webByVerse = new Map(web.verses.map((verse) => [`v${verse.verse}`, verse.text]));
const zomiRows = rows.filter((row) => !row.primary.startsWith("Not in "));
check("every TDB verse is shown once", zomiRows.length === tdb.verses.length, `${zomiRows.length} vs ${tdb.verses.length}`);
check("Zomi verses match the API word for word, in order", tdb.verses.every((verse, i) => zomiRows[i]?.id === `v${verse.verse}` && zomiRows[i]?.primary === verse.text));
check("English verses sit under the matching Zomi verse", zomiRows.every((row) => !webByVerse.has(row.id) || row.secondary.includes(webByVerse.get(row.id))));
const joined = await page.$eval("#v17", (li) => ({ num: li.querySelector(".sb-vnum")?.textContent, en: li.querySelector(".sb-secondary")?.textContent }));
check("TDB's joined verse 17-18 carries both English verses", joined.num === "17-18" && joined.en.includes(webByVerse.get("v17")) && joined.en.includes(webByVerse.get("v18")), joined.num);
check("no verse is marked missing when it is only joined", rows.every((row) => !row.primary.startsWith("Not in ")));
await shot(page, "desktop-1440-light");

// 2. Navigation keeps versions and crosses books.
await page.click('.sb-chapter-nav a[rel="next"]');
await page.waitForURL(/chapter=2/);
check("next chapter keeps v and compare", /v=tdb/.test(page.url()) && /compare=web/.test(page.url()), page.url());
await page.goto(`${BASE}/bible?v=tdb&compare=kjv&book=1&chapter=50`, { waitUntil: "networkidle" });
await page.click('.sb-chapter-nav a[rel="next"]');
await page.waitForURL(/book=2/);
check("Genesis 50 → Exodus 1 with KJV kept", /book=2&chapter=1/.test(page.url()) && /compare=kjv/.test(page.url()), page.url());
check("existing compare=kjv link shows KJV", (await page.textContent(".sb-version-line"))?.includes("King James"));
await page.goto(`${BASE}/bible?v=tdb&book=1&chapter=1`, { waitUntil: "networkidle" });
check("no previous link at Genesis 1", (await page.$$('.sb-chapter-nav a[rel="prev"]')).length === 0);

// 3. URL-selected display modes. A stale device preference must never hide an advertised version.
const visible = (selector) => page.$eval(selector, (el) => getComputedStyle(el).display !== "none");
await page.evaluate(() => localStorage.setItem("siamsil.bible.preferences", JSON.stringify({ mode: "primary", theme: "light", fontSize: 18, lineHeight: 1.8, typeface: "serif" })));
await page.reload({ waitUntil: "networkidle" });
check("stale primary-only preference cannot hide URL-selected WEB", (await visible(".sb-verse .sb-primary")) && (await visible(".sb-verse .sb-secondary")));
await page.click('button[aria-label="Reading settings"]');
await page.click("text=TDB only");
await page.waitForURL(/compare=none/);
check("TDB only shows Zomi", (await page.$$(".sb-verse .sb-secondary")).length === 0 && (await page.textContent("#v1 .sb-primary")) === tdb.verses[0].text);
await page.click('button[aria-label="Reading settings"]');
await page.click("text=WEB only");
await page.waitForURL(/v=web&compare=none/);
check("WEB only shows English", (await page.$$(".sb-verse .sb-secondary")).length === 0 && (await page.textContent("#v1 .sb-primary")) === web.verses[0].text);
await page.click('button[aria-label="Reading settings"]');
await page.click("text=TDB + WEB");
await page.waitForURL(/v=tdb&compare=web/);
check("TDB + WEB shows both", (await visible(".sb-verse .sb-primary")) && (await visible(".sb-verse .sb-secondary")));
await page.reload({ waitUntil: "networkidle" });
check("refresh preserves selected versions", /v=tdb&compare=web/.test(page.url()) && (await visible(".sb-verse .sb-secondary")));

// 4. Theme, font size and line height persist across reloads, applied before hydration.
await page.click('button[aria-label="Reading settings"]');
await page.click("text=Dark");
await page.click('.sb-stepper button[aria-label="Larger text"]');
await page.click('.sb-stepper button[aria-label="More line spacing"]');
await page.keyboard.press("Escape");
const bgDark = await page.$eval(".sb-root", (el) => getComputedStyle(el).backgroundColor);
check("dark theme changes the page", bgDark === "rgb(10, 22, 40)", bgDark);
await shot(page, "desktop-1440-dark");
await page.reload({ waitUntil: "domcontentloaded" });
const early = await page.evaluate(() => [document.documentElement.getAttribute("data-bible-theme"), document.documentElement.style.getPropertyValue("--sb-font-size"), document.documentElement.style.getPropertyValue("--sb-line-height")]);
check("saved theme and type apply on first paint (no flash)", early[0] === "dark" && early[1] === "19px" && early[2] === "1.9", early.join(" "));
await page.waitForLoadState("networkidle");
await page.click('button[aria-label="Reading settings"]');
await page.click("text=Sepia");
await page.keyboard.press("Escape");
await shot(page, "desktop-1440-sepia");
await page.click('button[aria-label="Reading settings"]');
await page.click("text=Light");
await page.keyboard.press("Escape");

// 5. A genuinely unavailable compared chapter is explained, never fabricated.
await page.goto(`${BASE}/bible?v=web&compare=tb77&book=2&chapter=1`, { waitUntil: "networkidle" });
check("missing compared chapter has an unavailable notice", (await page.textContent(".sb-alert-soft"))?.includes("couldn't be loaded") && (await page.$$(".sb-verse .sb-secondary")).length === 0);
await page.goto(`${BASE}/bible?v=tdb&compare=web&book=19&chapter=119`, { waitUntil: "networkidle" });
check("missing TDB verse is marked missing beside original WEB", (await page.textContent("#v2 .sb-primary"))?.includes("Not in TDB") && (await page.textContent("#v2 .sb-secondary"))?.length > 0);

// 6. Verse actions with the mouse: copy, bookmark, highlight, note; persistence; saved panel.
await page.goto(`${BASE}/bible?v=tdb&book=1&chapter=1`, { waitUntil: "networkidle" });
await page.evaluate(() => localStorage.removeItem("siamsil.bible.saved"));
await page.reload({ waitUntil: "networkidle" });
await page.click("#v3 .sb-vbody");
check("tapping a verse selects it and opens actions", (await page.$("#v3.is-selected")) !== null && (await page.$(".sb-actions")) !== null);
await shot(page, "desktop-1440-selected");
await page.click('.sb-actions >> text=Copy');
const clip = await page.evaluate(() => navigator.clipboard.readText());
check("copy includes text, reference and versions", clip.includes(tdb.verses[2].text) && clip.includes("Piancilna 1:3") && clip.includes("TDB · WEB"), JSON.stringify(clip.slice(-40)));
await page.evaluate(() => Object.defineProperty(navigator, "share", { value: undefined, configurable: true }));
await page.click('.sb-actions >> text=Share');
await page.waitForFunction(() => document.querySelector(".sb-toast")?.textContent?.startsWith("Copied link"));
const shareToast = await page.textContent(".sb-toast");
const sharedClip = await page.evaluate(() => navigator.clipboard.readText());
check("share falls back to a canonical verse link", shareToast?.includes("Copied link") && sharedClip.includes("/bible?v=tdb&compare=web&book=1&chapter=1#v3"), `${shareToast} ${sharedClip.slice(-100)}`);
await page.click('.sb-actions >> text=Bookmark');
await page.click('.sb-actions button[aria-label="Highlight Green"]');
await page.click('.sb-actions >> text=Note');
await page.fill(".sb-textarea", "Pasian piangsak — read again <b>not html</b>");
await page.click("text=Save note");
await page.reload({ waitUntil: "networkidle" });
check("bookmark persists", (await page.$("#v3 .sb-marks svg")) !== null);
check("highlight persists", (await page.$("#v3.sb-hl-green")) !== null);
check("note persists as plain text", (await page.textContent("#v3 .sb-note"))?.includes("<b>not html</b>"));
await page.click('button[aria-label="Bookmarks and notes"]');
check("saved panel lists the bookmark", (await page.textContent(".sb-saved"))?.includes("Piancilna 1:3"));
await page.fill('input[placeholder="Find a saved reference"]', "not-a-reference");
check("saved references can be filtered", (await page.textContent("#sb-saved-list"))?.includes("No saved references match"));
await page.fill('input[placeholder="Find a saved reference"]', "Piancilna");
await shot(page, "desktop-1440-saved");
await page.click(".sb-saved-link");
await page.waitForURL(/#v3/);
check("saved item jumps to its verse", page.url().endsWith("#v3"), page.url());

// 7. Keyboard: select a verse, act, close with Escape and return focus.
await page.goto(`${BASE}/bible?v=tdb&book=1&chapter=1`, { waitUntil: "networkidle" });
await page.focus("#v5-num");
await page.keyboard.press("Enter");
const focusedInToolbar = await page.evaluate(() => document.activeElement?.closest(".sb-actions") !== null);
check("Enter on a verse number selects it and moves focus to the actions", focusedInToolbar && (await page.$("#v5.is-selected")) !== null);
await page.keyboard.press("Escape");
check("Escape closes actions and returns focus to the verse", (await page.$(".sb-actions")) === null && (await page.evaluate(() => document.activeElement?.id)) === "v5-num");

// 8. Book and chapter picker: search, arrow keys, navigation.
await page.click(".sb-pill-book");
await page.fill(".sb-book-search", "paikh");
check("book search finds Paikhiatna", (await page.textContent(".sb-books"))?.includes("Paikhiatna"));
await page.focus('.sb-chapters a:nth-child(1)');
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowDown");
check("arrow keys move through the chapter grid", (await page.evaluate(() => document.activeElement?.textContent)) === "7");
await page.keyboard.press("Enter");
await page.waitForURL(/book=2&chapter=7/);
check("choosing a chapter opens it", (await page.textContent("#sb-chapter-title"))?.includes("Paikhiatna 7"));

// 9. Focus Mode and scroll position.
await page.goto(`${BASE}/bible?v=tdb&compare=web&book=19&chapter=119`, { waitUntil: "networkidle" });
await page.locator("#v12").scrollIntoViewIfNeeded();
const beforeFocus = await page.$eval("#v12", (el) => el.getBoundingClientRect().top);
await page.click('button[aria-label="Enter Focus Mode"]');
check("Focus Mode hides global navigation and preserves scroll anchor", (await page.$eval(".desktop-sidebar", (el) => getComputedStyle(el).display)) === "none" && Math.abs((await page.$eval("#v12", (el) => el.getBoundingClientRect().top)) - beforeFocus) < 8);
check("progress reflects scrolling without marking completion", Number(await page.$eval(".sb-progress", (el) => el.getAttribute("aria-valuenow"))) > 0);
await shot(page, "desktop-1440-focus");
await page.click('button[aria-label="Exit Focus Mode"]');
check("Exit Focus Mode restores navigation", (await page.$eval(".desktop-sidebar", (el) => getComputedStyle(el).display)) !== "none");

// 10. Responsive widths: no sideways scrolling, controls reachable, bottom nav clear.
for (const width of [320, 375, 390, 430, 768, 1024, 1440]) {
  const p = await newPage(width, width < 800 ? 812 : 900);
  await p.goto(`${BASE}/bible?v=tdb&book=19&chapter=119`, { waitUntil: "networkidle" }); // long chapter
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const offenders = overflow > 0 ? await p.evaluate(() => [...document.querySelectorAll("body *")]
    .map((el) => ({ selector: `${el.tagName.toLowerCase()}.${String(el.className).replace(/\s+/g, ".").slice(0, 60)}`, right: Math.round(el.getBoundingClientRect().right) }))
    .filter((item) => item.right > innerWidth + 1).sort((a, b) => b.right - a.right).slice(0, 4)) : [];
  check(`no horizontal overflow at ${width}px`, overflow <= 0, `${overflow}px ${JSON.stringify(offenders)}`);
  if (width <= 430) {
    await p.click("#v1 .sb-vbody");
    const box = await p.$eval(".sb-actions", (el) => el.getBoundingClientRect().bottom);
    const nav = await p.$eval(".bottom-nav", (el) => el.getBoundingClientRect().top).catch(() => 9999);
    check(`actions sit above the bottom navigation at ${width}px`, box <= nav + 1, `${box} vs ${nav}`);
  }
  await shot(p, `w${width}`);
  if (width === 390) {
    await p.click('button[aria-label="Enter Focus Mode"]');
    check("mobile Focus Mode hides bottom navigation and keeps exit", (await p.$eval(".bottom-nav", (el) => getComputedStyle(el).display)) === "none" && (await p.$('button[aria-label="Exit Focus Mode"]')) !== null);
    await p.click('button[aria-label="Exit Focus Mode"]');
    await p.goto(`${BASE}/bible?v=tdb&compare=web&book=1&chapter=1`, { waitUntil: "networkidle" });
    await shot(p, "mobile-390-reader");
    await p.click(".sb-pill-book");
    await shot(p, "mobile-390-chapter-selector");
    await p.keyboard.press("Escape");
    await p.click("#v1 .sb-vbody");
    await shot(p, "mobile-390-verse-actions");
    await p.click('button[aria-label="Close verse actions"]');
    await p.click('button[aria-label="Reading settings"]');
    await shot(p, "mobile-390-preferences");
  }
  await p.context().close();
}

// 11. Scripture search: words, exact phrase, book filter, links back to the verse.
page = await newPage(1440);
await page.goto(`${BASE}/bible?v=tdb&book=1&chapter=1`, { waitUntil: "networkidle" });
await page.click('a[aria-label="Search the Bible"]');
await page.waitForURL(/\/bible\/search/);
await page.fill('.sb-search-form input[name="q"]', "khuavak om hen");
await page.check('.sb-search-form input[name="phrase"]');
await page.click('.sb-search-form button[type="submit"]');
await page.waitForURL(/q=khuavak/);
const expected = await api("/bible/versions/tdb/search?q=khuavak%20om%20hen&phrase=true&limit=20");
const shown = await page.$$eval(".sb-result", (items) => items.length);
check("phrase search shows the API's matches", expected.total > 0 && shown === Math.min(20, expected.total), `${shown} of ${expected.total}`);
check("matches are marked in the verse text", (await page.$$(".sb-result-text mark")).length > 0);
await shot(page, "search-1440");
await page.click(".sb-result-ref >> nth=0");
await page.waitForURL(/#v\d+/);
check("a result opens its chapter at the verse, bilingual kept", /compare=web/.test(page.url()) && /#v3$/.test(page.url()), page.url());
await page.goto(`${BASE}/bible/search?q=Pasian&v=tdb&book=40`, { waitUntil: "networkidle" });
const refs = await page.$$eval(".sb-result-ref", (items) => items.map((item) => item.textContent ?? ""));
check("book filter keeps results to that book", refs.length > 0 && refs.every((ref) => ref.startsWith("Matthai")), refs[0]);
check("results show how many pages there are", (await page.textContent(".sb-chapter-nav") ?? "").includes("Page 1 of"));

check("no page or console errors", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : "\nall checks passed");
process.exit(failures ? 1 : 0);
