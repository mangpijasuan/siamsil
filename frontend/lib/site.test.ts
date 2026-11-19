import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PUBLIC_PAGES,
  bibleChapterPath,
  forSitemapXml,
  robotsPolicy,
  siteUrl,
  sitemapEntries,
  websiteJsonLd,
} from "./site.ts";

test("site address is an https origin or nothing", () => {
  assert.equal(siteUrl("https://siamsil.org"), "https://siamsil.org");
  assert.equal(siteUrl(" https://siamsil.org/some/path/ "), "https://siamsil.org");
  assert.equal(siteUrl("https://www.siamsil.org:8443"), "https://www.siamsil.org:8443");
  for (const bad of [undefined, null, "", "   ", "siamsil.org", "http://siamsil.org", "https://user:pw@siamsil.org", "javascript:alert(1)"]) {
    assert.equal(siteUrl(bad), null, String(bad));
  }
});

test("without a site address, nothing is indexed and there is no sitemap", () => {
  assert.deepEqual(robotsPolicy(null), { rules: { userAgent: "*", disallow: "/" } });
  assert.deepEqual(sitemapEntries(null, [{ id: "tdb", books: [{ book_id: 1, chapters: [1] }] }]), []);
});

test("with a site address, robots allows the site, keeps personal pages out, and names the sitemap", () => {
  assert.deepEqual(robotsPolicy("https://siamsil.org"), {
    rules: { userAgent: "*", allow: "/", disallow: ["/profile", "/workspace", "/api/"] },
    sitemap: "https://siamsil.org/sitemap.xml",
    host: "https://siamsil.org",
  });
});

test("the sitemap lists every public page with absolute addresses, never the profile", () => {
  const urls = sitemapEntries("https://siamsil.org").map((entry) => entry.url);
  assert.equal(urls.length, PUBLIC_PAGES.length);
  assert.equal(urls[0], "https://siamsil.org");
  assert.ok(urls.includes("https://siamsil.org/zomidictionary"));
  assert.ok(urls.every((url) => url.startsWith("https://siamsil.org")));
  assert.ok(!urls.some((url) => url.includes("/profile") || url.includes("/workspace")));
});

test("Bible chapters get one stable address each, without the companion version", () => {
  assert.equal(bibleChapterPath("tdb", 40, 5), "/bible?v=tdb&book=40&chapter=5");
  const entries = sitemapEntries("https://siamsil.org", [
    { id: "tdb", books: [{ book_id: 1, chapters: [1, 2] }, { book_id: 40, chapters: [5] }] },
  ]);
  const chapters = entries.slice(PUBLIC_PAGES.length).map((entry) => entry.url);
  assert.deepEqual(chapters, [
    "https://siamsil.org/bible?v=tdb&book=1&chapter=1",
    "https://siamsil.org/bible?v=tdb&book=1&chapter=2",
    "https://siamsil.org/bible?v=tdb&book=40&chapter=5",
  ]);
});

test("structured data names the site and its dictionary search, and cannot close its script tag", () => {
  const json = websiteJsonLd("https://siamsil.org");
  const data = JSON.parse(json);
  assert.equal(data["@type"], "WebSite");
  assert.equal(data.url, "https://siamsil.org/");
  assert.equal(data.potentialAction.target.urlTemplate, "https://siamsil.org/zomidictionary?q={search_term_string}");
  assert.ok(!json.includes("<"));
});

test("sitemap URLs are escaped for XML, so query strings keep the sitemap valid", () => {
  const [entry] = forSitemapXml([{ url: "https://siamsil.org/bible?v=tdb&book=1&chapter=1", priority: 0.5 }]);
  assert.equal(entry.url, "https://siamsil.org/bible?v=tdb&amp;book=1&amp;chapter=1");
  assert.equal(entry.priority, 0.5);
  assert.equal(forSitemapXml([{ url: "https://siamsil.org/a'<b>\"" }])[0].url, "https://siamsil.org/a&apos;&lt;b&gt;&quot;");
});
