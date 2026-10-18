import Link from "next/link";
import type { BibleVersionBook, BibleVersionChapter, BibleVersionInfo } from "@/lib/api";
import BibleReaderBar from "./BibleReaderBar";
import { bibleHref, bookLabel } from "./bibleHref";

type Props = {
  versions: BibleVersionInfo[];
  version: BibleVersionInfo;
  compare: BibleVersionInfo | null;
  books: BibleVersionBook[];
  book: BibleVersionBook | null;
  chapter: number;
  primary: BibleVersionChapter | null;
  secondary: BibleVersionChapter | null;
  error: string | null;
};

function ChevronIcon({ flip = false }: { flip?: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={flip ? { transform: "scaleX(-1)" } : undefined}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

export default function BibleVersionReader({
  versions, version, compare, books, book, chapter, primary, secondary, error,
}: Props) {
  const link = (next: { book: number; chapter: number }) =>
    bibleHref({ v: version.id, compare: compare?.id, ...next });

  // Previous/next chapter, crossing into the neighbouring book at either end.
  const bookIndex = book ? books.findIndex((item) => item.book_id === book.book_id) : -1;
  const position = book ? book.chapters.indexOf(chapter) : -1;
  const previousBook = bookIndex > 0 ? books[bookIndex - 1] : null;
  const nextBook = bookIndex >= 0 && bookIndex < books.length - 1 ? books[bookIndex + 1] : null;
  const previous = book && position > 0
    ? { book: book.book_id, chapter: book.chapters[position - 1] }
    : previousBook && previousBook.chapters.length
      ? { book: previousBook.book_id, chapter: previousBook.chapters[previousBook.chapters.length - 1] }
      : null;
  const next = book && position >= 0 && position < book.chapters.length - 1
    ? { book: book.book_id, chapter: book.chapters[position + 1] }
    : nextBook && nextBook.chapters.length
      ? { book: nextBook.book_id, chapter: nextBook.chapters[0] }
      : null;

  // Compare mode keeps verse-by-verse rows; show every verse either version has.
  const primaryByVerse = new Map(primary?.verses.map((verse) => [verse.verse, verse]) ?? []);
  const secondaryByVerse = new Map(secondary?.verses.map((verse) => [verse.verse, verse]) ?? []);
  const verseNumbers = [...new Set([...primaryByVerse.keys(), ...secondaryByVerse.keys()])].sort((a, b) => a - b);

  return (
    <div className="br-root">
      <BibleReaderBar versions={versions} version={version} compare={compare} books={books} book={book} chapter={chapter} />

      {error && <div className="bv-error" role="alert">{error}</div>}

      {book && primary && (
        <article className="br-page" aria-label={`${bookLabel(book)} ${chapter}`}>
          <p className="br-version">{version.name}</p>
          <h1 className="font-playfair br-title">{bookLabel(book)} {chapter}</h1>

          {compare ? (
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
                      {other && <p className="bv-compare" lang={compare.language_iso ?? undefined}>{other.text}</p>}
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="br-text" lang={version.language_iso ?? undefined}>
              {primary.verses.map((verse) => (
                <span key={verse.verse} id={`v${verse.verse}`} className="br-verse">
                  <sup className="br-num">{verse.label}</sup>{verse.text}{" "}
                </span>
              ))}
            </p>
          )}

          <p className="bv-rights">
            {version.copyright || version.description}
            {compare && <><br />{compare.copyright || compare.description}</>}
          </p>
        </article>
      )}

      {previous && (
        <Link href={link(previous)} className="br-float br-float-prev" aria-label="Previous chapter"><ChevronIcon flip /></Link>
      )}
      {next && (
        <Link href={link(next)} className="br-float br-float-next" aria-label="Next chapter"><ChevronIcon /></Link>
      )}
    </div>
  );
}
