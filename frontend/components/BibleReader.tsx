"use client";
import { useState, useEffect } from "react";
import { getBibleChapter, BibleBook, BibleVerse } from "@/lib/api";

type Props = {
  books: BibleBook[];
  activeTestament: string;
  bookId: number | null;
  chapter: number;
};

const LANG_LABELS = ["Zomi", "English", "Side-by"];

export default function BibleReader({ books, activeTestament, bookId: initialBookId, chapter: initialChapter }: Props) {
  const filtered = books
    .filter(b =>
      activeTestament === "old"
        ? b.testament.toLowerCase().includes("old")
        : b.testament.toLowerCase().includes("new")
    )
    .filter((b, i, arr) => arr.findIndex(x => x.book_english === b.book_english) === i);

  const [selectedBookId, setSelectedBookId] = useState<number | null>(initialBookId ?? filtered[0]?.book_id ?? null);
  const [selectedChapter, setSelectedChapter] = useState(initialChapter);
  const [activeLang, setActiveLang] = useState(0);
  const [verses, setVerses] = useState<BibleVerse[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedBookId) return;
    let active = true;
    void (async () => {
      setLoading(true);
      try {
        const data = await getBibleChapter(selectedBookId, selectedChapter);
        if (active) setVerses(data.verses);
      } catch {
        if (active) setVerses([]);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedBookId, selectedChapter]);

  const selectedBook = books.find(b => b.book_id === selectedBookId);

  return (
    <>
      {/* Currently reading / chapter view */}
      {verses.length > 0 && (
        <div className="bible-current" style={{ marginTop: 14 }}>
          <div className="gold-label" style={{ marginBottom: 6 }}>Khat Zang in Na Dawng</div>
          <div className="font-playfair" style={{ fontSize: 18, fontWeight: 700, color: "var(--navy)" }}>
            {selectedBook?.book_english}
          </div>
          <div style={{ fontSize: 11, color: "var(--gray)", marginBottom: 10 }}>Chapter {selectedChapter} · {verses.length} verses</div>

          {/* Language display switcher */}
          <div style={{ background: "var(--cream)", borderRadius: 10, padding: "10px 12px", marginBottom: 12 }}>
            <div className="gold-label" style={{ marginBottom: 8 }}>Display Language</div>
            <div style={{ display: "flex", gap: 6 }}>
              {LANG_LABELS.map((l, i) => (
                <button
                  key={l}
                  onClick={() => setActiveLang(i)}
                  style={{
                    flex: 1, padding: 7, borderRadius: 8,
                    fontSize: 10, fontWeight: 600,
                    background: activeLang === i ? "var(--navy)" : "var(--white)",
                    color: activeLang === i ? "var(--white)" : "var(--navy)",
                    border: "1px solid var(--gray2)",
                    cursor: "pointer",
                  }}
                >{l}</button>
              ))}
            </div>
          </div>

          {/* Verses */}
          <div style={{ maxHeight: 280, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {loading ? (
              <div style={{ color: "var(--gray)", fontSize: 13, textAlign: "center", padding: 20 }}>Loading…</div>
            ) : verses.map(v => (
              <div key={v.verse} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: "var(--gold)", minWidth: 18, marginTop: 3 }}>{v.verse}</span>
                <div>
                  {(activeLang === 0 || activeLang === 3) && (
                    <p style={{ fontSize: 13, color: "var(--navy)", lineHeight: 1.6, margin: 0 }}>{v.zomi_iso}</p>
                  )}
                  {(activeLang === 2 || activeLang === 3) && v.english && (
                    <p style={{ fontSize: 12, color: "var(--gray)", lineHeight: 1.5, margin: activeLang === 3 ? "2px 0 0" : 0 }}>{v.english}</p>
                  )}
                  {activeLang === 1 && (
                    <p style={{ fontSize: 13, color: "var(--navy)", lineHeight: 1.6, margin: 0 }}>{v.zomi_original || v.zomi_iso}</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Chapter navigation */}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button
              onClick={() => setSelectedChapter(c => Math.max(1, c - 1))}
              style={{ flex: 1, padding: 8, borderRadius: 10, fontSize: 11, fontWeight: 600, background: "var(--cream)", color: "var(--navy)", border: "none", cursor: "pointer" }}
            >← Prev</button>
            <button
              onClick={() => setSelectedChapter(c => c + 1)}
              style={{ flex: 1, padding: 8, borderRadius: 10, fontSize: 11, fontWeight: 600, background: "var(--navy)", color: "var(--white)", border: "none", cursor: "pointer" }}
            >Next →</button>
          </div>
        </div>
      )}

      {/* Books grid */}
      <div className="section-header" style={{ paddingTop: 16 }}>
        <span className="section-title">Books</span>
        <span className="section-link" onClick={() => setSelectedBookId(null)}>All →</span>
      </div>

      <div className="books-grid">
        {filtered.map(b => (
          <button
            key={`${b.book_id}-${b.book_english}`}
            onClick={() => { setSelectedBookId(b.book_id); setSelectedChapter(1); }}
            className={`book-chip${selectedBookId === b.book_id ? " active" : ""}`}
            style={{ textAlign: "left", background: selectedBookId === b.book_id ? "var(--navy)" : "var(--white)" }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, color: selectedBookId === b.book_id ? "var(--white)" : "var(--navy)", marginBottom: 2 }}>
              {b.book_english}
            </div>
            <div className="book-chip-zomi">
              {b.book_zomi}
            </div>
          </button>
        ))}
      </div>
    </>
  );
}
