"use client";

import { useEffect, useState } from "react";
import { ApiError, getBibleChapter } from "@/lib/api";
import type { BibleBook, BibleVerse } from "@/lib/api";

type Props = {
  books: BibleBook[];
  activeTestament: "old" | "new";
  bookId: number | null;
  chapter: number;
};

type TextVersion = "zomi_iso" | "zomi_original" | "english";
const TEXT_VERSIONS: { id: TextVersion; label: string; short: string }[] = [
  { id: "zomi_iso", label: "Zomi · standardized", short: "Zomi" },
  { id: "zomi_original", label: "Zomi · source spelling", short: "Original Zomi" },
  { id: "english", label: "English · supplied text", short: "English" },
];
const SAVED_VERSES_KEY = "siamsil_saved_verses_v1";

function verseText(verse: BibleVerse, version: TextVersion): string {
  if (version === "zomi_original") return verse.zomi_original || verse.zomi_iso;
  if (version === "english") return verse.english || "English text is unavailable for this verse.";
  return verse.zomi_iso;
}

function versionLabel(version: TextVersion): string {
  return TEXT_VERSIONS.find((item) => item.id === version)?.short ?? "Zomi";
}

export default function BibleReader({ books, activeTestament, bookId, chapter }: Props) {
  const availableBooks = books.filter((book) => book.testament.toLowerCase().includes(activeTestament));
  const initialBook = availableBooks.find((book) => book.book_id === bookId) ?? availableBooks[0];
  const [selectedBookId, setSelectedBookId] = useState<number | null>(initialBook?.book_id ?? null);
  const [selectedChapter, setSelectedChapter] = useState(
    Number.isInteger(chapter) && chapter > 0 ? Math.min(chapter, initialBook?.chapter_count ?? 1) : 1,
  );
  const [primaryVersion, setPrimaryVersion] = useState<TextVersion>("zomi_iso");
  const [compareVersion, setCompareVersion] = useState<TextVersion>("english");
  const [comparing, setComparing] = useState(false);
  const [fontSize, setFontSize] = useState(18);
  const [bookQuery, setBookQuery] = useState("");
  const [selectedVerse, setSelectedVerse] = useState<number | null>(null);
  const [pendingJump, setPendingJump] = useState<number | null>(null);
  const [savedKeys, setSavedKeys] = useState<string[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [verses, setVerses] = useState<BibleVerse[]>([]);
  const [loading, setLoading] = useState(Boolean(initialBook));
  const [chapterError, setChapterError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        const value: unknown = JSON.parse(localStorage.getItem(SAVED_VERSES_KEY) ?? "[]");
        if (Array.isArray(value)) setSavedKeys(value.filter((item): item is string => typeof item === "string"));
      } catch {
        // A corrupt or disabled local store should not prevent reading.
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (selectedBookId === null) return;
    let active = true;
    void (async () => {
      setLoading(true);
      setChapterError(null);
      setVerses([]);
      try {
        const data = await getBibleChapter(selectedBookId, selectedChapter);
        if (active) setVerses(data.verses);
      } catch (error) {
        if (active) {
          setChapterError(error instanceof ApiError && error.status === 404
            ? "This chapter is not available in the supplied text. Choose another chapter."
            : "The chapter could not be loaded. Check your connection and try again.");
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [selectedBookId, selectedChapter, retryKey]);

  useEffect(() => {
    if (pendingJump === null || loading || !verses.some((verse) => verse.verse === pendingJump)) return;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(`bible-verse-${pendingJump}`)?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
        block: "center",
      });
      setPendingJump(null);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [pendingJump, loading, verses]);

  const selectedBook = availableBooks.find((book) => book.book_id === selectedBookId);
  const selectedBookIndex = availableBooks.findIndex((book) => book.book_id === selectedBookId);
  const chapterCount = selectedBook?.chapter_count ?? 1;
  const visibleBooks = availableBooks.filter((book) =>
    `${book.book_english} ${book.book_zomi}`.toLowerCase().includes(bookQuery.trim().toLowerCase()));
  const activeVerse = verses.find((verse) => verse.verse === selectedVerse);
  const savedInTestament = savedKeys.flatMap((key) => {
    const [bookIdValue, chapterValue, verseValue] = key.split(":").map(Number);
    const book = availableBooks.find((item) => item.book_id === bookIdValue);
    return book && Number.isInteger(chapterValue) && Number.isInteger(verseValue)
      ? [{ key, book, chapter: chapterValue, verse: verseValue }]
      : [];
  });
  const canGoPrevious = selectedChapter > 1 || selectedBookIndex > 0;
  const canGoNext = selectedChapter < chapterCount || selectedBookIndex < availableBooks.length - 1;

  function navigate(book: BibleBook, nextChapter: number, verseToSelect: number | null = null) {
    const locationChanged = book.book_id !== selectedBookId || nextChapter !== selectedChapter;
    setSelectedBookId(book.book_id);
    setSelectedChapter(nextChapter);
    setSelectedVerse(verseToSelect);
    setPendingJump(verseToSelect);
    setShowSaved(false);
    setActionMessage("");
    if (locationChanged) setLoading(true);
  }

  function changeVersion(version: TextVersion) {
    setPrimaryVersion(version);
    if (version === compareVersion) setCompareVersion(version === "english" ? "zomi_iso" : "english");
  }

  function adjacentChapter(direction: -1 | 1) {
    if (!selectedBook) return;
    if (direction === -1) {
      if (selectedChapter > 1) navigate(selectedBook, selectedChapter - 1);
      else if (selectedBookIndex > 0) {
        const previous = availableBooks[selectedBookIndex - 1];
        navigate(previous, previous.chapter_count);
      }
    } else if (selectedChapter < chapterCount) navigate(selectedBook, selectedChapter + 1);
    else if (selectedBookIndex < availableBooks.length - 1) navigate(availableBooks[selectedBookIndex + 1], 1);
  }

  function saveVerse(verse: BibleVerse) {
    if (!selectedBook) return;
    const key = `${selectedBook.book_id}:${selectedChapter}:${verse.verse}`;
    const alreadySaved = savedKeys.includes(key);
    const next = alreadySaved ? savedKeys.filter((item) => item !== key) : [...savedKeys, key];
    try {
      localStorage.setItem(SAVED_VERSES_KEY, JSON.stringify(next));
      setSavedKeys(next);
      setActionMessage(alreadySaved ? "Removed from saved verses on this device." : "Saved on this device.");
    } catch {
      setActionMessage("Could not save on this device. Check your browser storage settings.");
    }
  }

  async function copyVerse(verse: BibleVerse) {
    try {
      await navigator.clipboard.writeText(`${verseText(verse, primaryVersion)} — ${verse.reference} (${versionLabel(primaryVersion)})`);
      setActionMessage("Verse copied.");
    } catch {
      setActionMessage("Copy failed. You can select and copy the verse text manually.");
    }
  }

  if (!selectedBook) {
    return <div className="bible-reader-empty">Bible books are not available right now.</div>;
  }

  return (
    <div className="bible-workspace">
      <aside className="bible-book-rail" aria-label="Bible books">
        <div className="bible-rail-heading">
          <span>Browse books</span>
          <strong>{availableBooks.length}</strong>
        </div>
        <input type="search" value={bookQuery} onChange={(event) => setBookQuery(event.target.value)}
          placeholder="Find a book…" aria-label="Find a Bible book" />
        <div className="bible-rail-list">
          {visibleBooks.map((book) => (
            <button type="button" key={book.book_id} className={book.book_id === selectedBookId ? "active" : ""}
              aria-current={book.book_id === selectedBookId ? "true" : undefined}
              onClick={() => navigate(book, 1)}>
              <span>{book.book_english}</span><small>{book.book_zomi}</small>
            </button>
          ))}
          {visibleBooks.length === 0 && <p>No books match that search.</p>}
        </div>
      </aside>

      <div className="bible-reading-column">
        <section className="bible-reader-panel" aria-label="Bible reader">
          <div className="bible-reader-toolbar">
            <div className="bible-location-controls">
              <label>Book
                <select aria-label="Book" value={selectedBookId ?? ""} onChange={(event) => {
                  const book = availableBooks.find((item) => item.book_id === Number(event.target.value));
                  if (book) navigate(book, 1);
                }}>
                  {availableBooks.map((book) => <option key={book.book_id} value={book.book_id}>{book.book_english}</option>)}
                </select>
              </label>
              <label>Chapter
                <select aria-label="Chapter" value={selectedChapter}
                  onChange={(event) => navigate(selectedBook, Number(event.target.value))}>
                  {Array.from({ length: chapterCount }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}
                </select>
              </label>
            </div>
            <div className="bible-reading-tools">
              <button type="button" className="bible-saved-toggle" aria-expanded={showSaved}
                onClick={() => setShowSaved((value) => !value)}>★ <span>Saved</span> {savedInTestament.length}</button>
              <div className="bible-font-controls" role="group" aria-label="Verse text size">
                <button type="button" aria-label="Decrease text size" disabled={fontSize <= 15} onClick={() => setFontSize((size) => Math.max(15, size - 1))}>A−</button>
                <button type="button" aria-label="Increase text size" disabled={fontSize >= 24} onClick={() => setFontSize((size) => Math.min(24, size + 1))}>A+</button>
              </div>
            </div>
          </div>

          {showSaved && <div className="bible-saved-panel" aria-label="Saved verses in this testament">
            <strong>Saved verses · {activeTestament === "old" ? "Old" : "New"} Testament</strong>
            {savedInTestament.length === 0 ? <p>No verses saved here yet. Select a verse, then choose “Save verse.”</p> :
              <div>{savedInTestament.map(({ key, book, chapter: savedChapter, verse: savedVerse }) =>
                <button type="button" key={key} onClick={() => navigate(book, savedChapter, savedVerse)}>
                  {book.book_english} {savedChapter}:{savedVerse} →
                </button>)}</div>}
          </div>}

          <div className="bible-version-controls">
            <label>Reading text
              <select aria-label="Reading text" value={primaryVersion}
                onChange={(event) => changeVersion(event.target.value as TextVersion)}>
                {TEXT_VERSIONS.map((version) => <option key={version.id} value={version.id}>{version.label}</option>)}
              </select>
            </label>
            <button type="button" className={comparing ? "bible-compare active" : "bible-compare"}
              aria-pressed={comparing} onClick={() => setComparing((value) => !value)}>
              {comparing ? "Close compare" : "Compare texts"}
            </button>
            {comparing && <label>Compare with
              <select aria-label="Compare with" value={compareVersion}
                onChange={(event) => setCompareVersion(event.target.value as TextVersion)}>
                {TEXT_VERSIONS.filter((version) => version.id !== primaryVersion).map((version) =>
                  <option key={version.id} value={version.id}>{version.label}</option>)}
              </select>
            </label>}
          </div>

          <div className="bible-chapter-heading">
            <span className="bible-page-kicker">{selectedBook.book_zomi}</span>
            <h2 className="font-playfair">{selectedBook.book_english} {selectedChapter}</h2>
            <p>{versionLabel(primaryVersion)}{comparing ? ` + ${versionLabel(compareVersion)}` : ""} · {verses.length ? `${verses.length} verses` : "Scripture reader"}</p>
          </div>

          {comparing && <div className="bible-compare-legend" aria-label="Comparison columns">
            <span>{versionLabel(primaryVersion)}</span><span>{versionLabel(compareVersion)}</span>
          </div>}

          <div className="bible-verses" style={{ ["--bible-font-size" as string]: `${fontSize}px` }}>
            {loading ? (
              <div className="bible-reader-state" role="status">Loading chapter…</div>
            ) : chapterError ? (
              <div className="bible-reader-state bible-reader-error" role="alert">
                <p>{chapterError}</p>
                <button type="button" onClick={() => setRetryKey((value) => value + 1)}>Try again</button>
              </div>
            ) : verses.length === 0 ? (
              <div className="bible-reader-state">No verses are available for this chapter.</div>
            ) : verses.map((verse) => {
              const key = `${selectedBook.book_id}:${selectedChapter}:${verse.verse}`;
              return (
                <div className="bible-verse-wrap" id={`bible-verse-${verse.verse}`} key={verse.verse}>
                  <button type="button"
                    className={`bible-verse${selectedVerse === verse.verse ? " selected" : ""}${savedKeys.includes(key) ? " saved" : ""}`}
                    aria-pressed={selectedVerse === verse.verse}
                    aria-label={`Select ${verse.reference}`}
                    onClick={() => { setSelectedVerse(selectedVerse === verse.verse ? null : verse.verse); setActionMessage(""); }}>
                    <span className="bible-verse-number">{verse.verse}</span>
                    <span className={comparing ? "bible-verse-texts comparing" : "bible-verse-texts"}>
                      <span className="bible-verse-primary">{verseText(verse, primaryVersion)}</span>
                      {comparing && <span className="bible-verse-secondary" lang={compareVersion === "english" ? "en" : undefined}>
                        {verseText(verse, compareVersion)}
                      </span>}
                    </span>
                    {savedKeys.includes(key) && <span className="bible-saved-mark" aria-label="Saved verse">★</span>}
                  </button>
                  {selectedVerse === verse.verse && (
                    <div className="bible-verse-actions">
                      <strong>{verse.reference}</strong>
                      <button type="button" onClick={() => void copyVerse(verse)}>Copy verse</button>
                      <button type="button" onClick={() => saveVerse(verse)}>
                        {savedKeys.includes(key) ? "Remove saved" : "Save verse"}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {activeVerse && actionMessage && <p className="bible-action-message" role="status">{actionMessage}</p>}
          <nav className="bible-chapter-nav" aria-label="Chapter navigation">
            <button type="button" disabled={!canGoPrevious || loading} onClick={() => adjacentChapter(-1)}>← Previous chapter</button>
            <span>{selectedChapter} of {chapterCount}</span>
            <button type="button" disabled={!canGoNext || loading} onClick={() => adjacentChapter(1)}>Next chapter →</button>
          </nav>
        </section>
        <p className="bible-source-note">The Zomi choices are standardized and source-spelling forms of the supplied text—not separate published editions. The English edition is not identified in the source data. Saved verses stay on this device.</p>
      </div>
    </div>
  );
}
