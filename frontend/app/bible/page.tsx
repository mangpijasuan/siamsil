import Link from "next/link";
import BibleReader from "@/components/BibleReader";
import BibleVersionReader, { bibleHref } from "@/components/BibleVersionReader";
import {
  describeApiError,
  getBibleBooks,
  getBibleVersionBooks,
  getBibleVersionChapter,
  getBibleVersions,
} from "@/lib/api";
import type { BibleVersionChapter, BibleVersionInfo } from "@/lib/api";

type Props = {
  searchParams: Promise<{ book?: string; chapter?: string; testament?: string; v?: string; compare?: string }>;
};

function positiveInt(value: string | undefined) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
}

async function loadVersions(): Promise<BibleVersionInfo[]> {
  try {
    return (await getBibleVersions()).versions;
  } catch {
    return [];
  }
}

export default async function BiblePage({ searchParams }: Props) {
  const params = await searchParams;
  const versions = await loadVersions();

  if (versions.length === 0) return <WorkbookBible {...params} />;

  const version = versions.find((item) => item.id === params.v) ?? versions[0];
  const compare = versions.find((item) => item.id === params.compare && item.id !== version.id) ?? null;
  let error: string | null = null;
  let books: Awaited<ReturnType<typeof getBibleVersionBooks>>["books"] = [];
  try {
    books = (await getBibleVersionBooks(version.id)).books;
  } catch (caught) {
    error = describeApiError(caught, "Bible");
  }

  const requested = books.find((item) => item.book_id === positiveInt(params.book));
  const book = requested ?? books[0] ?? null;
  const chapter = requested ? Math.min(positiveInt(params.chapter) ?? 1, requested.chapter_count) : 1;
  const testament = params.testament === "new" || params.testament === "old"
    ? params.testament
    : book?.testament === "new" ? "new" : "old";

  let primary: BibleVersionChapter | null = null;
  let secondary: BibleVersionChapter | null = null;
  if (book) {
    const [first, second] = await Promise.allSettled([
      getBibleVersionChapter(version.id, book.book_id, chapter),
      compare ? getBibleVersionChapter(compare.id, book.book_id, chapter) : Promise.resolve(null),
    ]);
    if (first.status === "fulfilled") primary = first.value;
    else error = describeApiError(first.reason, "Bible");
    if (second.status === "fulfilled") secondary = second.value;
  }

  const tab = (value: "old" | "new") => bibleHref({ v: version.id, compare: compare?.id, book: book?.book_id, chapter, testament: value });

  return (
    <>
      <header className="page-header-compact">
        <span className="font-playfair" style={{ color: "var(--white)", fontSize: 20, fontWeight: 700 }}>Bible Hub</span>
        <div className="testament-tabs">
          <Link href={tab("old")} className={`testament-tab${testament === "old" ? " active" : ""}`}>Old Testament</Link>
          <Link href={tab("new")} className={`testament-tab${testament === "new" ? " active" : ""}`}>New Testament</Link>
        </div>
      </header>

      <BibleVersionReader
        versions={versions}
        version={version}
        compare={compare}
        books={books}
        testament={testament}
        book={book}
        chapter={chapter}
        primary={primary}
        secondary={secondary}
        error={error}
      />

      <div className="screen-pad" />
    </>
  );
}

// Reader for the workbook Bible, used when no Bible versions database is loaded.
async function WorkbookBible({ book, chapter, testament }: { book?: string; chapter?: string; testament?: string }) {
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

      {error && <div className="bv-error" role="alert">{error}</div>}

      <BibleReader books={books} activeTestament={activeTestament} bookId={book ? Number(book) : null} chapter={chapter ? Number(chapter) : 1} />

      <div className="screen-pad" />
    </>
  );
}
