/**
 * Search-engine facts about the public site. Pure functions, so they can be unit-tested
 * without Next.js.
 *
 * The public address comes from SIAMSIL_SITE_URL at build time (e.g. https://siamsil.com).
 * Without it (local runs, preview builds) the site asks search engines not to index anything,
 * so a half-configured deployment never ends up in search results.
 */

export type ChangeFrequency = "daily" | "weekly" | "monthly" | "yearly";

export type SitemapEntry = { url: string; changeFrequency: ChangeFrequency; priority: number };

export type RobotsPolicy = {
  rules: { userAgent: string; allow?: string; disallow: string | string[] };
  sitemap?: string;
  host?: string;
};

/** The site's public origin, or null when unset or not an absolute https address. */
export function siteUrl(value: string | undefined | null): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (url.protocol !== "https:" || url.username || url.password) return null;
    return url.origin;
  } catch {
    return null;
  }
}

export const SITE_URL = siteUrl(process.env.SIAMSIL_SITE_URL);

export const SITE_NAME = "Siamsil";
export const SITE_DESCRIPTION =
  "Zomi dictionary, Zomi–English translation, the Zomi Bible, and lessons. The digital home for the Zomi language.";

/** Pages worth indexing. Profile is device-local and personal, so it is left out. */
export const PUBLIC_PAGES: { path: string; changeFrequency: ChangeFrequency; priority: number }[] = [
  { path: "/", changeFrequency: "weekly", priority: 1 },
  { path: "/zomidictionary", changeFrequency: "weekly", priority: 0.9 },
  { path: "/zomitranslate", changeFrequency: "weekly", priority: 0.9 },
  { path: "/bible", changeFrequency: "monthly", priority: 0.8 },
  { path: "/bible/search", changeFrequency: "monthly", priority: 0.5 },
  { path: "/learning", changeFrequency: "monthly", priority: 0.7 },
  { path: "/learning/citizenship", changeFrequency: "monthly", priority: 0.6 },
  { path: "/library", changeFrequency: "monthly", priority: 0.5 },
  { path: "/chat", changeFrequency: "monthly", priority: 0.4 },
];

export function robotsPolicy(site: string | null): RobotsPolicy {
  if (!site) return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/profile", "/api/"] },
    sitemap: `${site}/sitemap.xml`,
    host: site,
  };
}

/** The address of one Bible chapter in one version; the companion version is left out on purpose. */
export function bibleChapterPath(versionId: string, bookId: number, chapter: number): string {
  const params = new URLSearchParams({ v: versionId, book: String(bookId), chapter: String(chapter) });
  return `/bible?${params.toString()}`;
}

type SitemapBible = { id: string; books: { book_id: number; chapters: number[] }[] };

export function sitemapEntries(site: string | null, bibles: SitemapBible[] = []): SitemapEntry[] {
  if (!site) return [];
  const pages = PUBLIC_PAGES.map(({ path, changeFrequency, priority }) => ({
    url: `${site}${path === "/" ? "" : path}`,
    changeFrequency,
    priority,
  }));
  const chapters = bibles.flatMap(({ id, books }) =>
    books.flatMap(({ book_id, chapters: numbers }) =>
      numbers.map((chapter) => ({
        url: `${site}${bibleChapterPath(id, book_id, chapter)}`,
        changeFrequency: "yearly" as const,
        priority: 0.5,
      })),
    ),
  );
  return [...pages, ...chapters];
}

/**
 * Next.js writes sitemap URLs into the XML as given, so characters XML reserves must be escaped
 * first; a bare "&" (between query parameters) would make the whole sitemap invalid.
 */
export function forSitemapXml<T extends { url: string }>(entries: T[]): T[] {
  const escape = (text: string) =>
    text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
  return entries.map((entry) => ({ ...entry, url: escape(entry.url) }));
}

/**
 * schema.org description of the site, with the dictionary search as its site search.
 * Serialized for a <script type="application/ld+json">: "<" is escaped so text can never
 * close the script element.
 */
export function websiteJsonLd(site: string): string {
  const data = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    alternateName: "Siamsil Zomi Dictionary",
    url: `${site}/`,
    description: SITE_DESCRIPTION,
    potentialAction: {
      "@type": "SearchAction",
      target: { "@type": "EntryPoint", urlTemplate: `${site}/zomidictionary?q={search_term_string}` },
      "query-input": "required name=search_term_string",
    },
  };
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
