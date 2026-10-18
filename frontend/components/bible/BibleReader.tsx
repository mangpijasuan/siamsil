import Link from "next/link";
import type { BibleVersionBook, BibleVersionChapter, BibleVersionInfo } from "@/lib/api";
import { adjacentChapters, alignVerses, bibleHref, bookLabel, NO_COMPARE } from "@/lib/bible/references";
import BibleToolbar from "./BibleToolbar";
import BibleVerses from "./BibleVerses";
import { ChevronLeft, ChevronRight } from "./icons";

type Props = {
  versions: BibleVersionInfo[];
  version: BibleVersionInfo;
  compare: BibleVersionInfo | null;
  books: BibleVersionBook[];
  book: BibleVersionBook | null;
  chapter: number;
  primary: BibleVersionChapter | null;
  secondary: BibleVersionChapter | null;
  secondaryError: string | null;
  error: string | null;
};

const meta = (item: BibleVersionInfo) => ({
  id: item.id,
  abbreviation: item.abbreviation,
  languageIso: item.language_iso ?? null,
  languageName: item.language_name ?? null,
});

/** The Bible reading page: scripture is fetched and rendered on the server; only the controls are client code. */
export default function BibleReader({ versions, version, compare, books, book, chapter, primary, secondary, secondaryError, error }: Props) {
  const { previous, next } = book ? adjacentChapters(books, book.book_id, chapter) : { previous: null, next: null };
  const compareParam = compare?.id ?? NO_COMPARE;
  const link = (target: { book: number; chapter: number }) => bibleHref({ v: version.id, compare: compareParam, ...target });
  const rows = primary ? alignVerses(primary.verses, secondary?.verses ?? null) : [];
  const secondaryLanguage = compare ? compare.language_name || compare.abbreviation.toUpperCase() : null;

  return (
    <div className="sb-root">

      <BibleToolbar versions={versions} version={version} compare={compare} books={books} book={book} chapter={chapter} previous={previous} next={next} />

      <main className="sb-main" id="bible-text">
        {error && <div className="sb-alert" role="alert">{error}</div>}

        {book && primary && (
          <article className="sb-page" aria-labelledby="sb-chapter-title">
            <header className="sb-page-head">
              <p className="sb-version-line">
                {version.name}
                {compare && <> · <span className="sb-secondary-label">{compare.name}</span></>}
              </p>
              <h1 className="font-playfair sb-chapter-title" id="sb-chapter-title">{bookLabel(book)} {chapter}</h1>
              {book.name_local && <p className="sb-book-en-line">{book.name} {chapter}</p>}
            </header>

            {compare && secondaryError && (
              <p className="sb-alert sb-alert-soft" role="status">{compare.abbreviation.toUpperCase()} couldn&apos;t be loaded for this chapter: {secondaryError}</p>
            )}
            {!compare && (
              <p className="sb-alert sb-alert-soft sb-when-secondary" role="status">
                No version is chosen to show alongside {version.abbreviation.toUpperCase()}. Open Versions to pick one, or show {version.language_name || "the main text"}.
              </p>
            )}

            <BibleVerses
              key={`${version.id}-${book.book_id}-${chapter}`}
              rows={rows}
              book={book.book_id}
              bookName={bookLabel(book)}
              chapter={chapter}
              primary={meta(version)}
              secondary={compare && secondary ? meta(compare) : null}
            />

            <nav className="sb-chapter-nav" aria-label="Chapter navigation">
              {previous ? <Link href={link(previous)} className="sb-btn sb-btn-quiet" rel="prev"><ChevronLeft size={18} /> Previous</Link> : <span />}
              {next ? <Link href={link(next)} className="sb-btn sb-btn-primary" rel="next">Next <ChevronRight size={18} /></Link> : <span />}
            </nav>

            <footer className="sb-rights">
              <p>{version.copyright || version.description}</p>
              {compare && <p>{compare.copyright || compare.description}</p>}
              {secondaryLanguage && <p className="sr-only">Each verse shows {version.language_name} first, then {secondaryLanguage}.</p>}
            </footer>
          </article>
        )}
      </main>

      {previous && <Link href={link(previous)} className="sb-float sb-float-prev" aria-label="Previous chapter" rel="prev"><ChevronLeft size={22} /></Link>}
      {next && <Link href={link(next)} className="sb-float sb-float-next" aria-label="Next chapter" rel="next"><ChevronRight size={22} /></Link>}
    </div>
  );
}
