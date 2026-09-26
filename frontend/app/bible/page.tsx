import Link from "next/link";
import BibleReader from "@/components/BibleReader";
import { getBibleBooks } from "@/lib/api";

type Props = { searchParams: Promise<{ book?: string; chapter?: string; testament?: string }> };

export default async function BiblePage({ searchParams }: Props) {
  const { book, chapter, testament } = await searchParams;

  let books: Awaited<ReturnType<typeof getBibleBooks>>["books"] = [];
  let error: string | null = null;

  try {
    const data = await getBibleBooks();
    books = data.books;
  } catch {
    error = "Could not reach the API. Start the backend on port 8000.";
  }

  const activeTestament = testament === "new" ? "new" : "old";

  return (
    <>
      {/* ── Header ── */}
      <header className="page-header-compact">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="font-playfair" style={{ color: "var(--white)", fontSize: 20, fontWeight: 700 }}>Bible Hub</span>
          <span style={{ fontSize: 20 }}>⚙️</span>
        </div>

        {/* OT / NT tabs */}
        <div className="testament-tabs">
          <Link
            href="/bible?testament=old"
            className={`testament-tab${activeTestament === "old" ? " active" : ""}`}
          >Old Testament</Link>
          <Link
            href="/bible?testament=new"
            className={`testament-tab${activeTestament === "new" ? " active" : ""}`}
          >New Testament</Link>
        </div>
      </header>

      {error && (
        <div style={{ margin: "16px 16px 0", padding: "12px 16px", borderRadius: 12, background: "#FEE2E2", color: "#B91C1C", fontSize: 13 }}>
          {error}
        </div>
      )}

      <BibleReader books={books} activeTestament={activeTestament} bookId={book ? Number(book) : null} chapter={chapter ? Number(chapter) : 1} />

      <div className="screen-pad" />
    </>
  );
}
