import Link from "next/link";
import BibleReader from "@/components/BibleReader";
import { getBibleBooks } from "@/lib/api";
import "./bible.css";

type Props = { searchParams: Promise<{ book?: string; chapter?: string; testament?: string }> };

export default async function BiblePage({ searchParams }: Props) {
  const { book, chapter, testament } = await searchParams;

  let books: Awaited<ReturnType<typeof getBibleBooks>>["books"] = [];
  let error: string | null = null;

  try {
    const data = await getBibleBooks();
    books = data.books;
  } catch {
    error = "Bible books could not be loaded. Check your connection and try again.";
  }

  const activeTestament = testament === "new" ? "new" : "old";

  return (
    <>
      <header className="bible-page-hero">
        <div>
          <span className="bible-page-kicker">Siamsil · Scripture</span>
          <h1 className="font-playfair">Laisiangtho</h1>
          <p>Read the supplied Zomi and English texts in a calm, flexible reader.</p>
        </div>
        <nav className="bible-testament-tabs" aria-label="Bible testament">
          <Link
            href="/bible?testament=old"
            aria-current={activeTestament === "old" ? "page" : undefined}
            className={activeTestament === "old" ? "active" : ""}
          >Old Testament</Link>
          <Link
            href="/bible?testament=new"
            aria-current={activeTestament === "new" ? "page" : undefined}
            className={activeTestament === "new" ? "active" : ""}
          >New Testament</Link>
        </nav>
      </header>

      {error && (
        <div className="bible-page-error" role="alert">
          {error} <a href="/bible" style={{ color: "inherit", fontWeight: 700, textDecoration: "underline" }}>Retry</a>
        </div>
      )}

      {!error && <BibleReader key={activeTestament} books={books} activeTestament={activeTestament} bookId={book ? Number(book) : null} chapter={chapter ? Number(chapter) : 1} />}

      <div className="screen-pad" />
    </>
  );
}
