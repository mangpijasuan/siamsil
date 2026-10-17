import Link from "next/link";
import type { BibleVersionBook, BibleVersionChapter, BibleVersionInfo } from "@/lib/api";
import BibleVersionPicker from "./BibleVersionPicker";

type Props = {
  versions: BibleVersionInfo[];
  version: BibleVersionInfo;
  compare: BibleVersionInfo | null;
  books: BibleVersionBook[];
  testament: "old" | "new";
  book: BibleVersionBook | null;
  chapter: number;
  primary: BibleVersionChapter | null;
  secondary: BibleVersionChapter | null;
  error: string | null;
};

export function bibleHref(params: { v: string; compare?: string | null; book?: number; chapter?: number; testament?: string }) {
  const query = new URLSearchParams({ v: params.v });
  if (params.compare) query.set("compare", params.compare);
  if (params.book) query.set("book", String(params.book));
  if (params.chapter) query.set("chapter", String(params.chapter));
  if (params.testament) query.set("testament", params.testament);
  return `/bible?${query.toString()}`;
}

export default function BibleVersionReader({
  versions, version, compare, books, testament, book, chapter, primary, secondary, error,
}: Props) {
  const link = (next: { book?: number; chapter?: number; testament?: string }) =>
    bibleHref({ v: version.id, compare: compare?.id, ...next });
  // Show every verse either version has, so a verse missing from the primary is not lost.
  const primaryByVerse = new Map(primary?.verses.map((verse) => [verse.verse, verse]) ?? []);
  const secondaryByVerse = new Map(secondary?.verses.map((verse) => [verse.verse, verse]) ?? []);
  const verseNumbers = [...new Set([...primaryByVerse.keys(), ...secondaryByVerse.keys()])].sort((a, b) => a - b);
  const shownBooks = books.filter((item) => item.testament === testament);
  const position = book ? book.chapters.indexOf(chapter) : -1;
  const previous = book && position > 0 ? book.chapters[position - 1] : null;
  const next = book && position >= 0 && position < book.chapters.length - 1 ? book.chapters[position + 1] : null;

  return (
    <>
      <div className="bv-bar">
        <BibleVersionPicker versions={versions} version={version.id} compare={compare?.id ?? ""} book={book?.book_id} chapter={chapter} />
      </div>

      {error && <div className="bv-error" role="alert">{error}</div>}

      {book && primary && (
        <section className="bible-current bv-reading" aria-label={`${book.name} ${chapter}`}>
          <div className="gold-label" style={{ marginBottom: 6 }}>{version.name}</div>
          <h2 className="font-playfair bv-title">{book.name} {chapter}</h2>
          <div className="bv-sub">
            {primary.verse_count} verses
            {compare && <> · compared with {compare.abbreviation.toUpperCase()}</>}
          </div>

          <nav className="bv-chapters" aria-label="Chapters">
            {book.chapters.map((number) => (
              <Link
                key={number}
                href={link({ book: book.book_id, chapter: number })}
                className={`bv-chapter${number === chapter ? " active" : ""}`}
                aria-current={number === chapter ? "page" : undefined}
              >{number}</Link>
            ))}
          </nav>

          <ol className="bv-verses">
            {verseNumbers.map((number) => {
              const verse = primaryByVerse.get(number);
              const other = secondaryByVerse.get(number);
              return (
                <li key={number} className="bv-verse">
                  <span className="bv-num">{verse?.label ?? other?.label}</span>
                  <div>
                    {verse
                      ? <p className="bv-text" lang={version.language_iso ?? undefined}>{verse.text}</p>
                      : <p className="bv-missing">Not in {version.abbreviation.toUpperCase()}</p>}
                    {other && <p className="bv-compare" lang={compare?.language_iso ?? undefined}>{other.text}</p>}
                  </div>
                </li>
              );
            })}
          </ol>

          <div className="bv-nav">
            {previous
              ? <Link className="bv-nav-btn" href={link({ book: book.book_id, chapter: previous })}>← Prev</Link>
              : <span className="bv-nav-btn is-disabled">← Prev</span>}
            {next
              ? <Link className="bv-nav-btn bv-nav-next" href={link({ book: book.book_id, chapter: next })}>Next →</Link>
              : <span className="bv-nav-btn bv-nav-next is-disabled">Next →</span>}
          </div>

          <p className="bv-rights">
            {version.copyright || version.description}
            {compare && <><br />{compare.copyright || compare.description}</>}
          </p>
        </section>
      )}

      <div className="section-header" style={{ paddingTop: 16 }}>
        <span className="section-title">Books</span>
      </div>
      <div className="books-grid">
        {shownBooks.map((item) => {
          const active = item.book_id === book?.book_id;
          return (
            <Link
              key={item.book_id}
              href={link({ book: item.book_id, chapter: 1 })}
              className={`book-chip${active ? " active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: active ? "var(--white)" : "var(--navy)", marginBottom: 2 }}>
                {item.name}
              </div>
              <div className="book-chip-zomi">{item.chapter_count} chapters</div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
