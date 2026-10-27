import type { Metadata } from "next";
import Link from "next/link";
import { cache } from "react";
import BibleReader from "@/components/BibleReader";
import VersionReader from "@/components/bible/BibleReader";
import { chooseCompanion } from "@/lib/bible/references";
import "./bible.css";
import {
  ApiError,
  describeApiError,
  getBibleBooks,
  getBibleVersionBooks,
  getBibleVersionChapter,
  getBibleVersions,
} from "@/lib/api";
import type { BibleVersionBook, BibleVersionChapter, BibleVersionInfo } from "@/lib/api";
import { bibleChapterPath } from "@/lib/site";

type Props = {
  searchParams: Promise<{ book?: string; chapter?: string; testament?: string; v?: string; compare?: string }>;
};

function positiveInt(value: string | undefined) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
}

// 503 means no versions database is loaded: use the workbook reader. Other failures are errors.
// Cached per request, so the page and its metadata share one API call.
const loadVersions = cache(async (): Promise<{ versions: BibleVersionInfo[]; error: string | null }> => {
  try {
    return { versions: (await getBibleVersions()).versions, error: null };
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 503) return { versions: [], error: null };
    return { versions: [], error: describeApiError(caught, "Bible") };
  }
});

const loadBooks = cache(async (versionId: string): Promise<{ books: BibleVersionBook[]; error: string | null }> => {
  try {
    return { books: (await getBibleVersionBooks(versionId)).books, error: null };
  } catch (caught) {
    return { books: [], error: describeApiError(caught, "Bible") };
  }
});

type Params = Awaited<Props["searchParams"]>;

// A requested book decides the testament; otherwise the requested testament picks its first book.
function chooseChapter(books: BibleVersionBook[], params: Params): { book: BibleVersionBook | null; chapter: number } {
  const requested = books.find((item) => item.book_id === positiveInt(params.book));
  const requestedTestament = params.testament === "new" || params.testament === "old" ? params.testament : null;
  const book = requested
    ?? books.find((item) => item.testament === (requestedTestament ?? "old"))
    ?? books[0]
    ?? null;
  const wantedChapter = requested ? positiveInt(params.chapter) : null;
  const chapter = book
    ? (wantedChapter && book.chapters.includes(wantedChapter) ? wantedChapter : book.chapters[0] ?? 1)
    : 1;
  return { book, chapter };
}

// Each chapter of each version gets its own title and address, so search engines can list it.
export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const params = await searchParams;
  const { versions } = await loadVersions();
  const version = versions.find((item) => item.id === params.v) ?? versions[0];
  if (!version) return { title: "Zomi Bible", alternates: { canonical: "/bible" } };
  const { book, chapter } = chooseChapter((await loadBooks(version.id)).books, params);
  if (!book) return { title: `Bible (${version.abbreviation})`, alternates: { canonical: "/bible" } };
  const name = book.name_local || book.name;
  const language = version.language_iso === "ctd" ? "Zomi Bible" : "Bible";
  return {
    title: `${name} ${chapter} — ${language} (${version.abbreviation})`,
    // The English book name too, for people who search "Matthew 5 Zomi".
    description: `Read ${name}${name !== book.name ? ` (${book.name})` : ""} chapter ${chapter} in the ${version.name} on Siamsil.`,
    alternates: { canonical: bibleChapterPath(version.id, book.book_id, chapter) },
  };
}

export default async function BiblePage({ searchParams }: Props) {
  const params = await searchParams;
  const { versions, error: versionsError } = await loadVersions();

  if (versions.length === 0) return <WorkbookBible {...params} notice={versionsError} />;

  const version = versions.find((item) => item.id === params.v) ?? versions[0];
  // Bilingual by default: a Zomi version is paired with English unless the link says otherwise (compare=none).
  const compare = chooseCompanion(versions, version, params.compare);
  const loaded = await loadBooks(version.id);
  const books = loaded.books;
  let error: string | null = loaded.error;
  const { book, chapter } = chooseChapter(books, params);

  let primary: BibleVersionChapter | null = null;
  let secondary: BibleVersionChapter | null = null;
  let secondaryError: string | null = null;
  if (book) {
    const [first, second] = await Promise.allSettled([
      getBibleVersionChapter(version.id, book.book_id, chapter),
      compare ? getBibleVersionChapter(compare.id, book.book_id, chapter) : Promise.resolve(null),
    ]);
    if (first.status === "fulfilled") primary = first.value;
    else error = describeApiError(first.reason, "Bible");
    if (second.status === "fulfilled") secondary = second.value;
    else secondaryError = describeApiError(second.reason, "Bible");
  }

  return (
    <VersionReader
      versions={versions}
      version={version}
      compare={compare}
      books={books}
      book={book}
      chapter={chapter}
      primary={primary}
      secondary={secondary}
      secondaryError={secondaryError}
      error={error}
    />
  );
}

// Reader for the workbook Bible, used when no Bible versions database is loaded.
async function WorkbookBible({
  book, chapter, testament, notice,
}: { book?: string; chapter?: string; testament?: string; notice?: string | null }) {
  let books: Awaited<ReturnType<typeof getBibleBooks>>["books"] = [];
  let error: string | null = null;

  try {
    const data = await getBibleBooks();
    books = data.books;
  } catch (caught) {
    error = describeApiError(caught, "Bible");
  }

  const activeTestament = testament === "new" ? "new" : "old";

  return (
    <>
      <header className="page-header-compact">
        <span className="font-playfair" style={{ color: "var(--white)", fontSize: 20, fontWeight: 700 }}>Bible Hub</span>
        <div className="testament-tabs">
          <Link href="/bible?testament=old" className={`testament-tab${activeTestament === "old" ? " active" : ""}`}>Old Testament</Link>
          <Link href="/bible?testament=new" className={`testament-tab${activeTestament === "new" ? " active" : ""}`}>New Testament</Link>
        </div>
      </header>

      {(notice || error) && <div className="bv-error" role="alert">{notice || error}</div>}

      <BibleReader books={books} activeTestament={activeTestament} bookId={book ? Number(book) : null} chapter={chapter ? Number(chapter) : 1} />

      <div className="screen-pad" />
    </>
  );
}
