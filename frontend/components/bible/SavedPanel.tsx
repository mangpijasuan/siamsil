"use client";

import { useState } from "react";
import Link from "next/link";
import { useSavedData } from "@/lib/bible/hooks";
import { bibleHref } from "@/lib/bible/references";
import { refKey, saveNote, setHighlight, sortedByDate, toggleBookmark } from "@/lib/bible/savedData";
import type { VerseRef } from "@/lib/bible/savedData";
import Sheet from "./Sheet";

type Tab = "bookmarks" | "notes" | "highlights";

/** Everything saved on this device, with links back to each verse. */
export default function SavedPanel({ onClose, compareParam }: { onClose: () => void; compareParam: string }) {
  const { data, update } = useSavedData();
  const [tab, setTab] = useState<Tab>("bookmarks");
  const [query, setQuery] = useState("");
  const now = () => new Date().toISOString();

  const lists = {
    bookmarks: sortedByDate(Object.values(data.bookmarks)),
    notes: sortedByDate(Object.values(data.notes)),
    highlights: sortedByDate(Object.values(data.highlights)),
  };
  const href = (ref: VerseRef) => bibleHref({ v: ref.version, compare: compareParam, book: ref.book, chapter: ref.chapter }, ref.verse);
  const remove = (ref: VerseRef) => {
    if (tab === "bookmarks") update((current) => toggleBookmark(current, ref, now()));
    else if (tab === "notes") update((current) => saveNote(current, ref, "", now()));
    else update((current) => setHighlight(current, ref, null, now()));
  };
  const labels: Record<Tab, string> = { bookmarks: "Bookmarks", notes: "Notes", highlights: "Highlights" };
  const matches = lists[tab].filter((item) => {
    const text = `${item.label} ${item.version} ${"text" in item ? item.text : ""}`;
    return text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  });

  return (
    <Sheet title="Bookmarks and notes" onClose={onClose}>
      <div className="sb-tabs" role="tablist" aria-label="Saved items">
        {(Object.keys(labels) as Tab[]).map((key) => (
          <button key={key} type="button" role="tab" id={`sb-tab-${key}`} aria-selected={tab === key} aria-controls="sb-saved-list"
            className={`sb-tab${tab === key ? " is-on" : ""}`} onClick={() => setTab(key)}>
            {labels[key]} <span className="sb-count">{lists[key].length}</span>
          </button>
        ))}
      </div>
      <label className="sb-field">
        <span className="sr-only">Filter saved references</span>
        <input className="sb-input" type="search" value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder="Find a saved reference" autoComplete="off" />
      </label>
      <div id="sb-saved-list" role="tabpanel" aria-labelledby={`sb-tab-${tab}`}>
        {matches.length === 0 ? (
          <p className="sb-muted">
            {query ? `No saved references match “${query}”.` : (
              tab === "bookmarks" ? "No bookmarks yet. Tap a verse, then Bookmark."
                : tab === "notes" ? "No notes yet. Tap a verse, then Note."
                  : "No highlights yet. Tap a verse and pick a colour."
            )}
          </p>
        ) : (
          <ul className="sb-saved">
            {matches.map((item) => (
              <li key={refKey(item)} className="sb-saved-row">
                <Link href={href(item)} className="sb-saved-link" onClick={onClose}>
                  <strong>{item.label}</strong>
                  <span className="sb-saved-version">{item.version.toUpperCase()}</span>
                  {"text" in item && <span className="sb-saved-note">{item.text}</span>}
                  {"color" in item && <span className={`sb-swatch sb-hl-${item.color}`} aria-label={`${item.color} highlight`} />}
                </Link>
                <button type="button" className="sb-link-btn" onClick={() => remove(item)} aria-label={`Remove ${labels[tab].toLowerCase().replace(/s$/, "")} ${item.label}`}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="sb-muted">Saved in this browser only. They are not synced to other devices yet, and nothing here is sent to Siamsil.</p>
    </Sheet>
  );
}
