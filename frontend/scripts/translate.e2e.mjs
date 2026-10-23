// Browser checks for Zomi Translate's direction selector against a running app.
//   BASE=http://127.0.0.1:3002 API=http://127.0.0.1:8001 SHOTS=./shots node scripts/translate.e2e.mjs
// Needs Playwright with Chromium (e.g. `npx -y -p playwright@1 node scripts/translate.e2e.mjs`).
// Queries: "water" (an English headword) and "Pasian" (a Zomi word that is in the dictionary's
// Zomi definitions). Both come from Siamsil's own data; nothing here writes Zomi.
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
const search = async (q, direction) => {
  const params = new URLSearchParams({ q, limit: "20", ...(direction ? { direction } : {}) });
  return (await fetch(`${API}/api/v1/translate/search?${params}`)).json();
};
const shot = async (page, name, fullPage = false) => SHOTS && page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage });

const browser = await chromium.launch({ ...(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {}), args: ["--no-sandbox"] });
const errors = [];
const newPage = async (width, height = 900) => {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: width < 800 ? 2 : 1 });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  return page;
};
const settle = (page) => page.waitForLoadState("networkidle");
const selector = (page) => page.evaluate(() => [
  document.querySelector('[data-testid="source-language"]')?.textContent,
  document.querySelector('[data-testid="target-language"]')?.textContent,
]);
const best = (page) => page.evaluate(() => {
  const section = document.querySelector(".tr-result");
  if (!section) return null;
  const sides = [...section.querySelectorAll(".tr-result-side")];
  return {
    direction: section.getAttribute("data-direction"),
    labels: sides.map((side) => side.querySelector(".tr-side-label")?.textContent),
    texts: sides.map((side) => side.querySelector("p")?.textContent),
  };
});
const dirOf = (url) => new URL(url).searchParams.get("dir");
const qOf = (url) => new URL(url).searchParams.get("q");

// 1. English → Zomi: English first, Zomi second, matching the API's first result.
const waterEn = await search("water", "en-zom");
let page = await newPage(1440);
await page.goto(`${BASE}/zomitranslate?q=water&dir=en-zom`, { waitUntil: "networkidle" });
check("selector reads English → Zomi", JSON.stringify(await selector(page)) === '["English","Zomi"]');
let result = await best(page);
check("English → Zomi shows English then Zomi", result?.labels.join() === "English,Zomi", result?.labels.join());
check("English → Zomi text matches the API, source first",
  result?.texts[0] === waterEn.results[0].english && result?.texts[1] === waterEn.results[0].zomi);
await shot(page, "desktop-en-zom");

// 2. Zomi → English: Zomi first, English second, from a Zomi-side search.
const pasianZom = await search("Pasian", "zom-en");
await page.goto(`${BASE}/zomitranslate?q=Pasian&dir=zom-en`, { waitUntil: "networkidle" });
check("selector reads Zomi → English", JSON.stringify(await selector(page)) === '["Zomi","English"]');
result = await best(page);
check("Zomi → English shows Zomi then English", result?.labels.join() === "Zomi,English", result?.labels.join());
check("Zomi → English text matches the API, source first",
  pasianZom.count > 0 && result?.texts[0] === pasianZom.results[0].zomi && result?.texts[1] === pasianZom.results[0].english);
check("input is marked as Zomi for screen readers and spell-check",
  (await page.getAttribute("textarea.tr-input", "lang")) === "zom");
await shot(page, "desktop-zom-en");

// 3. The direction really filters: a Zomi word has no English-side match.
const pasianEn = await search("Pasian", "en-zom");
await page.goto(`${BASE}/zomitranslate?q=Pasian&dir=en-zom`, { waitUntil: "networkidle" });
const empty = await page.textContent(".tr-empty-title").catch(() => "");
check("Zomi word searched as English finds nothing", pasianEn.count === 0 && /No stored English → Zomi match/.test(empty), empty);
await shot(page, "desktop-no-match");
await page.click("text=Look it up Zomi → English instead");
await page.waitForURL((url) => dirOf(url.href) === "zom-en");
await settle(page);
result = await best(page);
check("no-match offers the other direction, which finds it", result?.direction === "zom-en", page.url());

// 4. Older links without a direction read as English → Zomi; the API keeps its two-sided default.
await page.goto(`${BASE}/zomitranslate?q=water`, { waitUntil: "networkidle" });
result = await best(page);
check("link without dir behaves as English → Zomi", result?.direction === "en-zom" && result?.texts[0] === waterEn.results[0].english);
const both = await search("water");
check("API without direction still searches both sides", both.count >= waterEn.count, `${both.count} vs ${waterEn.count}`);

// 5. Swap with a result: the translation becomes the input and the direction reverses.
await page.goto(`${BASE}/zomitranslate?q=water&dir=en-zom`, { waitUntil: "networkidle" });
const before = await best(page);
await page.click(".tr-swap");
await page.waitForURL((url) => dirOf(url.href) === "zom-en");
await settle(page);
check("swap reverses the direction in the URL", dirOf(page.url()) === "zom-en");
check("swap moves the translation into the input", qOf(page.url()) === before.texts[1] && (await page.inputValue("textarea.tr-input")) === before.texts[1], qOf(page.url()));
check("swap reverses the selector", JSON.stringify(await selector(page)) === '["Zomi","English"]');
result = await best(page);
check("after swap, results are labelled Zomi then English", !result || result.labels.join() === "Zomi,English", result?.labels.join());
await page.click(".tr-swap");
await page.waitForURL((url) => dirOf(url.href) === "en-zom");
await settle(page);
check("swapping back returns to English → Zomi", JSON.stringify(await selector(page)) === '["English","Zomi"]');

// 6. Swap with no result shown keeps the typed text.
await page.goto(`${BASE}/zomitranslate`, { waitUntil: "networkidle" });
await page.fill("textarea.tr-input", "water");
await page.click(".tr-swap");
await page.waitForURL((url) => dirOf(url.href) === "zom-en");
await settle(page);
check("swap before a lookup keeps the typed text", qOf(page.url()) === "water" && (await page.inputValue("textarea.tr-input")) === "water");

// 7. Fast switching: whatever lands, labels and results agree with each other and the URL.
await page.goto(`${BASE}/zomitranslate?q=water&dir=en-zom`, { waitUntil: "networkidle" });
for (let i = 0; i < 3; i += 1) await page.click(".tr-swap", { delay: 0, force: true });
await page.waitForTimeout(400);
await settle(page);
result = await best(page);
const sel = await selector(page);
const urlDir = dirOf(page.url());
const expectedLabels = urlDir === "en-zom" ? "English,Zomi" : "Zomi,English";
check("after fast switching, selector matches the URL", sel.join() === expectedLabels, `${sel.join()} / ${urlDir}`);
check("after fast switching, results match the URL", !result || (result.direction === urlDir && result.labels.join() === expectedLabels), `${result?.direction} / ${urlDir}`);

// 8. Keyboard: the swap button is a real button with a name.
await page.goto(`${BASE}/zomitranslate?q=water&dir=en-zom`, { waitUntil: "networkidle" });
await page.focus(".tr-swap");
check("swap button names the current direction", /Now English to Zomi/.test(await page.getAttribute(".tr-swap", "aria-label")));
await page.keyboard.press("Enter");
await page.waitForURL((url) => dirOf(url.href) === "zom-en");
check("Enter on the swap button swaps", dirOf(page.url()) === "zom-en");

// 9. Phone: no sideways scroll, a 44px swap target, both directions.
page = await newPage(390, 844);
for (const [q, dir] of [["water", "en-zom"], ["Pasian", "zom-en"]]) {
  await page.goto(`${BASE}/zomitranslate?q=${q}&dir=${dir}`, { waitUntil: "networkidle" });
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  const box = await page.locator(".tr-swap").boundingBox();
  check(`phone ${dir}: no sideways scroll, swap target ≥ 44px`, fits && box.width >= 44 && box.height >= 44, `${box.width}×${box.height}`);
  await shot(page, `mobile-${dir}`);
}

check("no page or console errors", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : "\nall checks passed");
process.exit(failures ? 1 : 0);
