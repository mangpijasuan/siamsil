"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { BibleVersionBook, BibleVersionInfo } from "@/lib/api";
import { pushRecentChapter, readRecentChapters } from "@/lib/localData";
import type { RecentChapter } from "@/lib/localData";
import { bibleHref } from "./bibleHref";

type Props = {
  versions: BibleVersionInfo[];
  version: BibleVersionInfo;
  compare: BibleVersionInfo | null;
  books: BibleVersionBook[];
  book: BibleVersionBook | null;
  chapter: number;
};

type Sheet = "books" | "versions" | null;

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function SheetFrame({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="bs-backdrop" onClick={onClose}>
      <div className="bs-sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <div className="bs-head">
          <button ref={closeRef} type="button" className="bs-round" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
          <h2 className="font-playfair bs-title">{title}</h2>
          <span className="bs-round-spacer" />
        </div>
        {children}
      </div>
    </div>
  );
}

export default function BibleReaderBar({ versions, version, compare, books, book, chapter }: Props) {
  const [sheet, setSheet] = useState<Sheet>(null);
  const [openBook, setOpenBook] = useState<number | null>(book?.book_id ?? null);
  const [recent, setRecent] = useState<RecentChapter[]>([]);
  const currentRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (!book) return;
    pushRecentChapter({ v: version.id, version: version.name, book: book.book_id, bookName: book.name, chapter });
  }, [version.id, version.name, book, chapter]);

  useEffect(() => {
    if (sheet === "books") currentRef.current?.scrollIntoView({ block: "center" });
  }, [sheet]);

  const close = () => setSheet(null);
  const link = (next: { v?: string; compare?: string | null; book?: number; chapter?: number }) =>
    bibleHref({ v: next.v ?? version.id, compare: "compare" in next ? next.compare : compare?.id, book: next.book ?? book?.book_id, chapter: next.chapter ?? chapter });

  const testaments: Array<["old" | "new", string]> = [["old", "Old Testament"], ["new", "New Testament"]];

  return (
    <>
      <div className="br-bar">
        <div className="br-pill">
          <button
            type="button"
            className="br-pill-book"
            onClick={() => {
              setOpenBook(book?.book_id ?? null);
              setRecent(readRecentChapters().slice(0, 6));
              setSheet("books");
            }}
          >
            {book ? `${book.name} ${chapter}` : "Books"}
          </button>
          <button type="button" className="br-pill-version" onClick={() => setSheet("versions")}>
            {version.abbreviation.toUpperCase()}
            {compare && <span className="br-pill-compare"> + {compare.abbreviation.toUpperCase()}</span>}
          </button>
        </div>
      </div>

      {sheet === "books" && (
        <SheetFrame title="Books" onClose={close}>
          <div className="bs-body">
            {testaments.map(([testament, label]) => {
              const group = books.filter((item) => item.testament === testament);
              if (group.length === 0) return null;
              return (
                <section key={testament} aria-label={label}>
                  <div className="bs-group">{label}</div>
                  <ul className="bs-books">
                    {group.map((item) => {
                      const expanded = openBook === item.book_id;
                      const current = item.book_id === book?.book_id;
                      return (
                        <li key={item.book_id} ref={current ? currentRef : undefined}>
                          <button
                            type="button"
                            className={`bs-book${expanded ? " is-open" : ""}${current ? " is-current" : ""}`}
                            aria-expanded={expanded}
                            onClick={() => setOpenBook(expanded ? null : item.book_id)}
                          >
                            {item.name}
                          </button>
                          {expanded && (
                            <div className="bs-chapters">
                              {item.chapters.map((number) => (
                                <Link
                                  key={number}
                                  href={link({ book: item.book_id, chapter: number })}
                                  className={`bs-chapter${current && number === chapter ? " is-current" : ""}`}
                                  aria-current={current && number === chapter ? "page" : undefined}
                                  onClick={close}
                                >{number}</Link>
                              ))}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              );
            })}
          </div>

          {recent.length > 0 && (
            <div className="bs-recents">
              <div className="bs-recents-title">Recents</div>
              <div className="bs-recents-row">
                {recent.map((item) => (
                  <Link
                    key={`${item.v}-${item.book}`}
                    href={bibleHref({ v: item.v, compare: compare?.id, book: item.book, chapter: item.chapter })}
                    className="bs-recent"
                    onClick={close}
                  >
                    <span className="bs-recent-ref">{item.bookName} {item.chapter}</span>
                    <span className="bs-recent-version">{item.version}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </SheetFrame>
      )}

      {sheet === "versions" && (
        <SheetFrame title="Versions" onClose={close}>
          <div className="bs-body">
            <div className="bs-group">Read</div>
            <ul className="bs-versions">
              {versions.map((item) => (
                <li key={item.id}>
                  <Link
                    href={link({ v: item.id, compare: compare?.id === item.id ? null : compare?.id })}
                    className={`bs-version${item.id === version.id ? " is-current" : ""}`}
                    aria-current={item.id === version.id ? "true" : undefined}
                    onClick={close}
                  >
                    <span className="bs-version-abbr">{item.abbreviation.toUpperCase()}</span>
                    <span className="bs-version-name">{item.name}</span>
                    {item.id === version.id && <CheckIcon />}
                  </Link>
                </li>
              ))}
            </ul>

            <div className="bs-group">Compare with</div>
            <ul className="bs-versions">
              <li>
                <Link href={link({ compare: null })} className={`bs-version${!compare ? " is-current" : ""}`} onClick={close}>
                  <span className="bs-version-abbr">—</span>
                  <span className="bs-version-name">None</span>
                  {!compare && <CheckIcon />}
                </Link>
              </li>
              {versions.filter((item) => item.id !== version.id).map((item) => (
                <li key={item.id}>
                  <Link
                    href={link({ compare: item.id })}
                    className={`bs-version${item.id === compare?.id ? " is-current" : ""}`}
                    onClick={close}
                  >
                    <span className="bs-version-abbr">{item.abbreviation.toUpperCase()}</span>
                    <span className="bs-version-name">{item.name}</span>
                    {item.id === compare?.id && <CheckIcon />}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </SheetFrame>
      )}
    </>
  );
}
