"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { BibleVersionBook, BibleVersionInfo } from "@/lib/api";
import { pushRecentChapter, readRecentChapters } from "@/lib/localData";
import type { RecentChapter } from "@/lib/localData";
import { useReadingPreferences } from "@/lib/bible/hooks";
import { bibleHref, bookLabel, filterBooks, NO_COMPARE } from "@/lib/bible/references";
import type { ChapterRef } from "@/lib/bible/references";
import { stepFontSize } from "@/lib/bible/preferences";
import type { ReadingPreferences } from "@/lib/bible/preferences";
import ReadingSettings from "./ReadingSettings";
import SavedPanel from "./SavedPanel";
import Sheet from "./Sheet";
import { BookmarkIcon, ChevronDown, ChevronLeft, ChevronRight, MoonIcon, SearchIcon, SepiaIcon, SettingsIcon, SunIcon } from "./icons";

type Props = {
  versions: BibleVersionInfo[];
  version: BibleVersionInfo;
  compare: BibleVersionInfo | null;
  books: BibleVersionBook[];
  book: BibleVersionBook | null;
  chapter: number;
  previous: ChapterRef | null;
  next: ChapterRef | null;
};

type Panel = "books" | "versions" | "settings" | "saved" | null;

const THEME_ORDER: ReadingPreferences["theme"][] = ["light", "sepia", "dark"];

export default function BibleToolbar({ versions, version, compare, books, book, chapter, previous, next }: Props) {
  const [panel, setPanel] = useState<Panel>(null);
  const { prefs, update } = useReadingPreferences();
  const close = useCallback(() => setPanel(null), []);
  // Links keep the compared version, or "none" when bilingual reading was turned off.
  const compareParam = compare?.id ?? NO_COMPARE;
  const link = (target: ChapterRef) => bibleHref({ v: version.id, compare: compareParam, ...target });

  useEffect(() => {
    if (book) pushRecentChapter({ v: version.id, version: version.name, book: book.book_id, bookName: bookLabel(book), chapter });
  }, [version.id, version.name, book, chapter]);

  const currentTheme = prefs.theme === "system" ? null : prefs.theme;
  const nextTheme = THEME_ORDER[(THEME_ORDER.indexOf(currentTheme ?? "light") + 1) % THEME_ORDER.length];
  const ThemeIcon = currentTheme === "dark" ? MoonIcon : currentTheme === "sepia" ? SepiaIcon : SunIcon;
  const reference = book ? `${bookLabel(book)} ${chapter}` : "Books";

  return (
    <>
      <div className="sb-toolbar" role="toolbar" aria-label="Bible reader">
        <div className="sb-toolbar-group">
          {previous
            ? <Link href={link(previous)} className="sb-icon-btn sb-desktop" aria-label="Previous chapter" rel="prev"><ChevronLeft /></Link>
            : <span className="sb-icon-btn sb-desktop is-disabled" aria-hidden="true"><ChevronLeft /></span>}
          <button type="button" className="sb-pill sb-pill-book" onClick={() => setPanel("books")} aria-haspopup="dialog">
            <span className="sb-pill-text">{reference}</span> <ChevronDown />
          </button>
          <button type="button" className="sb-pill sb-pill-version" onClick={() => setPanel("versions")} aria-haspopup="dialog"
            aria-label={`Versions: ${version.abbreviation.toUpperCase()}${compare ? ` with ${compare.abbreviation.toUpperCase()}` : ""}`}>
            {version.abbreviation.toUpperCase()}
            {compare && <span className="sb-pill-sub">+ {compare.abbreviation.toUpperCase()}</span>}
            <ChevronDown />
          </button>
          {next
            ? <Link href={link(next)} className="sb-icon-btn sb-desktop" aria-label="Next chapter" rel="next"><ChevronRight /></Link>
            : <span className="sb-icon-btn sb-desktop is-disabled" aria-hidden="true"><ChevronRight /></span>}
        </div>

        <div className="sb-toolbar-group">
          <button type="button" className="sb-icon-btn sb-desktop sb-text-btn" onClick={() => update({ fontSize: stepFontSize(prefs.fontSize, -1) })}
            disabled={prefs.fontSize <= 14} aria-label={`Smaller text (now ${prefs.fontSize} pixels)`}>A−</button>
          <button type="button" className="sb-icon-btn sb-desktop sb-text-btn sb-text-btn-lg" onClick={() => update({ fontSize: stepFontSize(prefs.fontSize, 1) })}
            disabled={prefs.fontSize >= 24} aria-label={`Larger text (now ${prefs.fontSize} pixels)`}>A+</button>
          <button type="button" className="sb-icon-btn sb-desktop" onClick={() => update({ theme: nextTheme })}
            aria-label={`Reading theme: ${currentTheme ?? "system"}. Switch to ${nextTheme}`}><ThemeIcon /></button>
          <button type="button" className="sb-icon-btn" onClick={() => setPanel("settings")} aria-haspopup="dialog" aria-label="Reading settings"><SettingsIcon /></button>
          <Link href={`/bible/search?v=${encodeURIComponent(version.id)}&compare=${encodeURIComponent(compareParam)}`} className="sb-icon-btn" aria-label="Search the Bible"><SearchIcon /></Link>
          <button type="button" className="sb-icon-btn" onClick={() => setPanel("saved")} aria-haspopup="dialog" aria-label="Bookmarks and notes"><BookmarkIcon /></button>
        </div>
      </div>

      {panel === "books" && <BooksSheet books={books} book={book} chapter={chapter} link={link} onClose={close} versionId={version.id} compareParam={compareParam} />}
      {panel === "versions" && <VersionsSheet versions={versions} version={version} compare={compare} book={book} chapter={chapter} onClose={close} />}
      {panel === "settings" && (
        <ReadingSettings prefs={prefs} update={update} onClose={close}
          primaryLanguage={version.language_name || version.abbreviation.toUpperCase()}
          secondaryLanguage={compare ? (compare.language_name || compare.abbreviation.toUpperCase()) : null} />
      )}
      {panel === "saved" && <SavedPanel onClose={close} compareParam={compareParam} />}
    </>
  );
}

function BooksSheet({ books, book, chapter, link, onClose, versionId, compareParam }: {
  books: BibleVersionBook[];
  book: BibleVersionBook | null;
  chapter: number;
  link: (target: ChapterRef) => string;
  onClose: () => void;
  versionId: string;
  compareParam: string;
}) {
  const [query, setQuery] = useState("");
  const [openBook, setOpenBook] = useState<number | null>(book?.book_id ?? null);
  const [recent] = useState<RecentChapter[]>(() => (typeof window === "undefined" ? [] : readRecentChapters().slice(0, 6)));
  const currentRef = useRef<HTMLLIElement>(null);
  const shown = filterBooks(books, query);

  useEffect(() => {
    currentRef.current?.scrollIntoView({ block: "center" });
  }, []);

  // Arrow keys move between chapter numbers in the 5-column grid.
  const onGridKey = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 5, ArrowUp: -5 };
    if (!(event.key in moves)) return;
    const items = [...event.currentTarget.querySelectorAll<HTMLAnchorElement>("a")];
    const index = items.indexOf(document.activeElement as HTMLAnchorElement);
    if (index < 0) return;
    event.preventDefault();
    items[Math.max(0, Math.min(items.length - 1, index + moves[event.key]))]?.focus();
  };

  const testaments: Array<["old" | "new", string]> = [["old", "Old Testament"], ["new", "New Testament"]];
  return (
    <Sheet title="Books" onClose={onClose} size="lg" initialFocus=".sb-book-search">
      <label className="sb-field">
        <span className="sr-only">Find a book</span>
        <input className="sb-input sb-book-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder="Find a book (Zomi or English name)" autoComplete="off" />
      </label>
      {recent.length > 0 && !query && (
        <div className="sb-recents" aria-label="Recently read">
          {recent.map((item) => (
            <Link key={`${item.v}-${item.book}`} href={bibleHref({ v: item.v, compare: compareParam, book: item.book, chapter: item.chapter })} className="sb-recent" onClick={onClose}>
              <strong>{item.bookName} {item.chapter}</strong>
              <span>{item.v === versionId ? "Recent" : item.v.toUpperCase()}</span>
            </Link>
          ))}
        </div>
      )}
      {shown.length === 0 && <p className="sb-muted">No book matches “{query}”.</p>}
      {testaments.map(([testament, label]) => {
        const group = shown.filter((item) => item.testament === testament);
        if (!group.length) return null;
        return (
          <section key={testament} aria-label={label}>
            <h3 className="sb-group-title">{label}</h3>
            <ul className="sb-books">
              {group.map((item) => {
                const expanded = openBook === item.book_id || (query !== "" && group.length === 1);
                const current = item.book_id === book?.book_id;
                return (
                  <li key={item.book_id} ref={current ? currentRef : undefined}>
                    <button type="button" className={`sb-book${current ? " is-current" : ""}`} aria-expanded={expanded}
                      onClick={() => setOpenBook(expanded ? null : item.book_id)}>
                      <span>{bookLabel(item)}</span>
                      {item.name_local && <span className="sb-book-en">{item.name}</span>}
                    </button>
                    {expanded && (
                      <div className="sb-chapters" role="group" aria-label={`${bookLabel(item)} chapters`} onKeyDown={onGridKey}>
                        {item.chapters.map((number) => {
                          const here = current && number === chapter;
                          return (
                            <Link key={number} href={link({ book: item.book_id, chapter: number })} className={`sb-chapter${here ? " is-current" : ""}`}
                              aria-current={here ? "page" : undefined} aria-label={`${bookLabel(item)} chapter ${number}`} onClick={onClose}>
                              {number}
                            </Link>
                          );
                        })}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </Sheet>
  );
}

function VersionsSheet({ versions, version, compare, book, chapter, onClose }: {
  versions: BibleVersionInfo[];
  version: BibleVersionInfo;
  compare: BibleVersionInfo | null;
  book: BibleVersionBook | null;
  chapter: number;
  onClose: () => void;
}) {
  const at = { book: book?.book_id, chapter };
  const row = (item: BibleVersionInfo, href: string, selected: boolean) => (
    <li key={item.id}>
      <Link href={href} className={`sb-version${selected ? " is-current" : ""}`} aria-current={selected ? "true" : undefined} onClick={onClose}>
        <span className="sb-version-abbr">{item.abbreviation.toUpperCase()}</span>
        <span className="sb-version-name">{item.name}<span className="sb-version-lang">{item.language_name}</span></span>
        {selected && <span className="sb-check" aria-hidden="true">✓</span>}
      </Link>
    </li>
  );
  return (
    <Sheet title="Versions" onClose={onClose}>
      <h3 className="sb-group-title">Read</h3>
      <ul className="sb-versions">
        {versions.map((item) => row(item, bibleHref({ v: item.id, compare: compare && compare.id !== item.id ? compare.id : undefined, ...at }), item.id === version.id))}
      </ul>
      <h3 className="sb-group-title">Show alongside</h3>
      <ul className="sb-versions">
        <li>
          <Link href={bibleHref({ v: version.id, compare: NO_COMPARE, ...at })} className={`sb-version${!compare ? " is-current" : ""}`} onClick={onClose}>
            <span className="sb-version-abbr">—</span>
            <span className="sb-version-name">None</span>
            {!compare && <span className="sb-check" aria-hidden="true">✓</span>}
          </Link>
        </li>
        {versions.filter((item) => item.id !== version.id).map((item) => row(item, bibleHref({ v: version.id, compare: item.id, ...at }), item.id === compare?.id))}
      </ul>
    </Sheet>
  );
}
