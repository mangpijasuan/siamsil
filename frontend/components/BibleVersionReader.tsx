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
  const secondaryByVerse = new Map(secondary?.verses.map((verse) => [verse.verse, verse]) ?? []);
  const shownBooks = books.filter((item) => item.testament === testament);

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
            {Array.from({ length: book.chapter_count }, (_, index) => index + 1).map((number) => (
              <Link
                key={number}
                href={link({ book: book.book_id, chapter: number })}
                className={`bv-chapter${number === chapter ? " active" : ""}`}
                aria-current={number === chapter ? "page" : undefined}
              >{number}</Link>
            ))}
          </nav>

          <ol className="bv-verses">
            {primary.verses.map((verse) => {
              const other = secondaryByVerse.get(verse.verse);
              return (
                <li key={verse.verse} className="bv-verse">
                  <span className="bv-num">{verse.label}</span>
                  <div>
                    <p className="bv-text" lang={version.language_iso ?? undefined}>{verse.text}</p>
                    {other && <p className="bv-compare" lang={compare?.language_iso ?? undefined}>{other.text}</p>}
                  </div>
                </li>
              );
            })}
          </ol>

          <div className="bv-nav">
            {chapter > 1
              ? <Link className="bv-nav-btn" href={link({ book: book.book_id, chapter: chapter - 1 })}>← Prev</Link>
              : <span className="bv-nav-btn is-disabled">← Prev</span>}
            {chapter < book.chapter_count
              ? <Link className="bv-nav-btn bv-nav-next" href={link({ book: book.book_id, chapter: chapter + 1 })}>Next →</Link>
              : <span className="bv-nav-btn bv-nav-next is-disabled">Next →</span>}
          </div>

          <p className="bv-rights">
            {version.copyright || version.description}
            {compare && <><br />{compare.copyright || compare.description}</>}
            <br />Shown for reading only. Permission to publish these texts is still being confirmed.
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
