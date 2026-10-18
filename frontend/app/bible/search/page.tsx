import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { describeApiError, getBibleVersionBooks, getBibleVersions, searchBibleVersion } from "@/lib/api";
import type { BibleVersionInfo, BibleVersionSearch } from "@/lib/api";
import { bibleHref, bookLabel, formatReference, NO_COMPARE } from "@/lib/bible/references";
import "../bible.css";

export const metadata: Metadata = { title: "Search the Bible" };

const PAGE_SIZE = 20;

type Props = {
  searchParams: Promise<{ q?: string; v?: string; compare?: string; book?: string; phrase?: string; page?: string }>;
};

/** Mark every occurrence of the search words in a verse, as React text (never HTML). */
function markMatches(text: string, terms: string[]): ReactNode {
  const words = terms.map((term) => term.trim()).filter(Boolean).sort((a, b) => b.length - a.length);
  if (!words.length) return text;
  const pattern = new RegExp(`(${words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(pattern).map((part, index) => (index % 2 === 1 ? <mark key={index}>{part}</mark> : part));
}

export default async function BibleSearchPage({ searchParams }: Props) {
  const params = await searchParams;
  const query = (params.q ?? "").trim().slice(0, 100);
  const phrase = params.phrase === "1";
  const page = Math.max(1, Math.min(250, Number(params.page) || 1));

  let versions: BibleVersionInfo[] = [];
  let error: string | null = null;
  try {
    versions = (await getBibleVersions()).versions;
  } catch (caught) {
    error = describeApiError(caught, "Bible");
  }
  const version = versions.find((item) => item.id === params.v) ?? versions[0] ?? null;
  const compare = params.compare ?? null;

  let books: Array<{ book_id: number; name: string; name_local?: string | null }> = [];
  let result: BibleVersionSearch | null = null;
  const bookId = Number(params.book) || undefined;
  if (version) {
    const [bookList, found] = await Promise.allSettled([
      getBibleVersionBooks(version.id),
      query.length >= 2 ? searchBibleVersion(version.id, { q: query, phrase, bookId, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }) : Promise.resolve(null),
    ]);
    if (bookList.status === "fulfilled") books = bookList.value.books;
    if (found.status === "fulfilled") result = found.value;
    else error = describeApiError(found.reason, "Bible search");
  }

  const pages = result ? Math.ceil(result.total / PAGE_SIZE) : 0;
  const pageHref = (target: number) => {
    const next = new URLSearchParams({ q: query, v: version?.id ?? "" });
    if (compare) next.set("compare", compare);
    if (bookId) next.set("book", String(bookId));
    if (phrase) next.set("phrase", "1");
    next.set("page", String(target));
    return `/bible/search?${next.toString()}`;
  };
  const terms = phrase ? [query] : query.split(/\s+/);

  return (
    <div className="sb-root">
      <main className="sb-main">
        <section className="sb-page sb-search-page" aria-labelledby="sb-search-title">
          <p className="sb-version-line">Bible search</p>
          <h1 className="font-playfair sb-chapter-title" id="sb-search-title">Search the Bible</h1>

          <form className="sb-search-form" action="/bible/search" method="GET" role="search">
            <label className="sb-field sb-search-q">
              <span className="sb-group-title">Words or phrase</span>
              <input className="sb-input" type="search" name="q" defaultValue={query} minLength={2} maxLength={100} required
                placeholder="e.g. Pasian, khuavak, light" />
            </label>
            <label className="sb-field">
              <span className="sb-group-title">Version</span>
              <select className="sb-input" name="v" defaultValue={version?.id}>
                {versions.map((item) => <option key={item.id} value={item.id}>{item.abbreviation.toUpperCase()} · {item.name}</option>)}
              </select>
            </label>
            <label className="sb-field">
              <span className="sb-group-title">Book</span>
              <select className="sb-input" name="book" defaultValue={bookId ? String(bookId) : ""}>
                <option value="">All books</option>
                {books.map((item) => <option key={item.book_id} value={item.book_id}>{bookLabel(item)}{item.name_local ? ` (${item.name})` : ""}</option>)}
              </select>
            </label>
            <label className="sb-check-field">
              <input type="checkbox" name="phrase" value="1" defaultChecked={phrase} /> Exact phrase
            </label>
            {compare && <input type="hidden" name="compare" value={compare} />}
            <button type="submit" className="sb-btn sb-btn-primary">Search</button>
          </form>

          {error && <p className="sb-alert" role="alert">{error}</p>}

          {result && (
            <div aria-live="polite">
              <p className="sb-search-count">
                {result.total === 0
                  ? `No verses in ${version?.abbreviation.toUpperCase()} contain “${query}”.`
                  : `${result.total.toLocaleString()} verse${result.total === 1 ? "" : "s"} in ${version?.name}${bookId ? ` · ${bookLabel(books.find((b) => b.book_id === bookId) ?? { name: "" })}` : ""}`}
              </p>
              <ol className="sb-results">
                {result.results.map((hit) => {
                  const reference = formatReference(bookLabel(hit), hit.chapter, hit.label);
                  return (
                    <li key={`${hit.book_id}-${hit.chapter}-${hit.verse}`} className="sb-result">
                      <Link href={bibleHref({ v: result!.version.id, compare: compare ?? (result!.version.language_iso === "eng" ? NO_COMPARE : undefined), book: hit.book_id, chapter: hit.chapter }, hit.verse)} className="sb-result-ref">
                        {reference} <span className="sb-saved-version">{result!.version.abbreviation.toUpperCase()}</span>
                      </Link>
                      <p className="sb-result-text" lang={result!.version.language_iso ?? undefined}>{markMatches(hit.text, terms)}</p>
                    </li>
                  );
                })}
              </ol>
              {pages > 1 && (
                <nav className="sb-chapter-nav" aria-label="Search result pages">
                  {page > 1 ? <Link className="sb-btn sb-btn-quiet" href={pageHref(page - 1)} rel="prev">← Previous</Link> : <span />}
                  <span className="sb-muted">Page {page} of {pages}</span>
                  {page < pages ? <Link className="sb-btn sb-btn-primary" href={pageHref(page + 1)} rel="next">Next →</Link> : <span />}
                </nav>
              )}
            </div>
          )}

          <p className="sb-muted">Bible search covers scripture only. Dictionary words are searched on the Dictionary page.</p>
          {version && (
            <p><Link href={bibleHref({ v: version.id, compare: compare ?? undefined })} className="sb-link-back">← Back to reading</Link></p>
          )}
        </section>
      </main>
    </div>
  );
}
