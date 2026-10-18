"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSavedData } from "@/lib/bible/hooks";
import { formatReference } from "@/lib/bible/references";
import type { AlignedVerse, VerseLike } from "@/lib/bible/references";
import { HIGHLIGHT_COLORS, NOTE_MAX_LENGTH, refKey, saveNote, setHighlight, shareText, toggleBookmark } from "@/lib/bible/savedData";
import type { HighlightColor, VerseRef } from "@/lib/bible/savedData";
import Sheet from "./Sheet";
import { BookmarkIcon, CloseIcon, CopyIcon, NoteIcon, ShareIcon } from "./icons";

type VersionMeta = { id: string; abbreviation: string; languageIso: string | null; languageName: string | null };

type Props = {
  rows: AlignedVerse[];
  book: number;
  bookName: string;
  chapter: number;
  primary: VersionMeta;
  secondary: VersionMeta | null;
};

const COLOR_NAMES: Record<HighlightColor, string> = { gold: "Gold", green: "Green", blue: "Blue", rose: "Rose" };

export default function BibleVerses({ rows, book, bookName, chapter, primary, secondary }: Props) {
  const { data, update } = useSavedData();
  const [selected, setSelected] = useState<number | null>(null);
  const [noteFor, setNoteFor] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const toolbarRef = useRef<HTMLDivElement>(null);
  const focusToolbar = useRef(false);

  const refFor = useCallback((row: AlignedVerse): VerseRef => ({
    version: primary.id, book, chapter, verse: row.verse, label: formatReference(bookName, chapter, row.label),
  }), [primary.id, book, chapter, bookName]);

  useEffect(() => {
    if (selected !== null && focusToolbar.current) {
      toolbarRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
      focusToolbar.current = false;
    }
  }, [selected]);

  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(""), 3200);
    return () => window.clearTimeout(timer);
  }, [message]);

  const clearSelection = useCallback(() => {
    const verse = selected;
    setSelected(null);
    if (verse !== null) document.getElementById(`v${verse}-num`)?.focus();
  }, [selected]);

  useEffect(() => {
    if (selected === null || noteFor !== null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") clearSelection();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selected, noteFor, clearSelection]);

  const select = (verse: number, fromKeyboard: boolean) => {
    if (selected === verse) {
      setSelected(null);
      return;
    }
    focusToolbar.current = fromKeyboard;
    setSelected(verse);
  };

  // Tapping the text selects the verse, unless the reader is selecting text to copy.
  const onTextClick = (verse: number) => {
    if (window.getSelection()?.toString()) return;
    select(verse, false);
  };

  const row = rows.find((item) => item.verse === selected) ?? null;
  const ref = row ? refFor(row) : null;
  const key = ref ? refKey(ref) : "";
  const now = () => new Date().toISOString();
  const saveFailed = "Couldn't save on this device. Storage may be full or turned off.";

  // Text for copy and share follows what is on screen: both versions, or one.
  const versesText = () => {
    if (!row) return "";
    const mode = document.documentElement.getAttribute("data-bible-mode") ?? "both";
    const parts: string[] = [];
    const labels: string[] = [];
    if (row.primary.length && mode !== "secondary") { parts.push(joinText(row.primary)); labels.push(primary.abbreviation.toUpperCase()); }
    if (row.secondary.length && secondary && mode !== "primary") { parts.push(joinText(row.secondary)); labels.push(secondary.abbreviation.toUpperCase()); }
    if (!parts.length && row.primary.length) { parts.push(joinText(row.primary)); labels.push(primary.abbreviation.toUpperCase()); }
    return shareText(parts.join("\n"), ref!.label, labels.join(" · "));
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(versesText());
      setMessage(`Copied ${ref!.label}`);
    } catch {
      setMessage("Couldn't copy. Select the text and copy it instead.");
    }
  };

  const share = async () => {
    const text = versesText();
    if (navigator.share) {
      try {
        await navigator.share({ title: ref!.label, text });
        return;
      } catch (error) {
        if ((error as DOMException)?.name === "AbortError") return;
      }
    }
    await copy();
  };

  const bookmark = () => {
    const had = Boolean(data.bookmarks[key]);
    if (!update((current) => toggleBookmark(current, ref!, now()))) return setMessage(saveFailed);
    setMessage(had ? `Removed bookmark ${ref!.label}` : `Bookmarked ${ref!.label}`);
  };

  const highlight = (color: HighlightColor) => {
    const removing = data.highlights[key]?.color === color;
    if (!update((current) => setHighlight(current, ref!, color, now()))) return setMessage(saveFailed);
    setMessage(removing ? "Highlight removed" : `Highlighted ${COLOR_NAMES[color].toLowerCase()}`);
  };

  return (
    <>
      <ol className="sb-verses">
        {rows.map((item) => {
          const itemKey = refKey(refFor(item));
          const isSelected = item.verse === selected;
          const color = data.highlights[itemKey]?.color;
          const note = data.notes[itemKey];
          const marked = Boolean(data.bookmarks[itemKey]);
          return (
            <li key={item.verse} id={`v${item.verse}`} className={`sb-verse${isSelected ? " is-selected" : ""}${color ? ` sb-hl-${color}` : ""}`}>
              <button type="button" id={`v${item.verse}-num`} className="sb-vnum" aria-pressed={isSelected}
                aria-label={`${formatReference(bookName, chapter, item.label)}${marked ? ", bookmarked" : ""}${color ? `, highlighted ${color}` : ""}${note ? ", has a note" : ""}. ${isSelected ? "Selected" : "Select verse"}`}
                onClick={(event) => select(item.verse, event.detail === 0)}>
                {item.label}
              </button>
              <div className="sb-vbody" onClick={() => onTextClick(item.verse)}>
                {item.primary.length
                  ? <p className="sb-primary" lang={primary.languageIso ?? undefined}><VerseParts parts={item.primary} /></p>
                  : <p className="sb-primary sb-missing">Not in {primary.abbreviation.toUpperCase()}</p>}
                {secondary && (item.secondary.length
                  ? <p className="sb-secondary" lang={secondary.languageIso ?? undefined}><VerseParts parts={item.secondary} /></p>
                  : <p className="sb-secondary sb-missing">Not in {secondary.abbreviation.toUpperCase()}</p>)}
                {note && <p className="sb-note"><NoteIcon size={14} /><span className="sr-only">Your note: </span>{note.text}</p>}
              </div>
              {(marked || color) && (
                <span className="sb-marks" aria-hidden="true">
                  {marked && <BookmarkIcon size={15} filled />}
                  {color && <span className={`sb-swatch sb-hl-${color}`} />}
                </span>
              )}
            </li>
          );
        })}
      </ol>

      {row && ref && (
        <div ref={toolbarRef} className="sb-actions" role="toolbar" aria-label={`Actions for ${ref.label}`}>
          <div className="sb-actions-head">
            <span className="sb-actions-ref">{ref.label}</span>
            <button type="button" className="sb-icon-btn" onClick={clearSelection} aria-label="Close verse actions"><CloseIcon size={18} /></button>
          </div>
          <div className="sb-actions-row">
            <button type="button" className="sb-action" onClick={copy}><CopyIcon size={18} /><span>Copy</span></button>
            <button type="button" className="sb-action" onClick={share}><ShareIcon size={18} /><span>Share</span></button>
            <button type="button" className={`sb-action${data.bookmarks[key] ? " is-on" : ""}`} onClick={bookmark} aria-pressed={Boolean(data.bookmarks[key])}>
              <BookmarkIcon size={18} filled={Boolean(data.bookmarks[key])} /><span>{data.bookmarks[key] ? "Saved" : "Bookmark"}</span>
            </button>
            <button type="button" className={`sb-action${data.notes[key] ? " is-on" : ""}`} onClick={() => setNoteFor(row.verse)}>
              <NoteIcon size={18} /><span>{data.notes[key] ? "Edit note" : "Note"}</span>
            </button>
            <span className="sb-swatches" role="group" aria-label="Highlight colour">
              {HIGHLIGHT_COLORS.map((color) => (
                <button key={color} type="button" className={`sb-swatch-btn sb-hl-${color}`} onClick={() => highlight(color)}
                  aria-pressed={data.highlights[key]?.color === color} aria-label={`Highlight ${COLOR_NAMES[color]}`}>
                  {data.highlights[key]?.color === color && <span aria-hidden="true">✓</span>}
                </button>
              ))}
            </span>
          </div>
        </div>
      )}

      {noteFor !== null && row && ref && (
        <NoteEditor
          reference={ref.label}
          initial={data.notes[key]?.text ?? ""}
          onCancel={() => setNoteFor(null)}
          onSave={(text) => {
            if (!update((current) => saveNote(current, ref, text, now()))) return setMessage(saveFailed);
            setNoteFor(null);
            setMessage(text.trim() ? `Note saved for ${ref.label}` : "Note deleted");
          }}
        />
      )}

      <p className="sb-toast" role="status" aria-live="polite">{message}</p>
    </>
  );
}

/** One verse's text, or several (when the other version joins them) each with its own small number. */
function VerseParts({ parts }: { parts: VerseLike[] }) {
  if (parts.length === 1) return <>{parts[0].text}</>;
  return (
    <>
      {parts.map((part, index) => (
        <span key={part.verse}>
          {index > 0 && " "}
          <sup className="sb-part-num">{part.label}</sup>
          {part.text}
        </span>
      ))}
    </>
  );
}

function joinText(parts: VerseLike[]) {
  return parts.length === 1 ? parts[0].text : parts.map((part) => `[${part.label}] ${part.text}`).join(" ");
}

function NoteEditor({ reference, initial, onSave, onCancel }: {
  reference: string;
  initial: string;
  onSave: (text: string) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(initial);
  return (
    <Sheet title={`Note on ${reference}`} onClose={onCancel} size="sm" initialFocus="textarea"
      footer={
        <>
          {initial && <button type="button" className="sb-btn sb-btn-quiet" onClick={() => onSave("")}>Delete</button>}
          <button type="button" className="sb-btn sb-btn-quiet" onClick={onCancel}>Cancel</button>
          <button type="button" className="sb-btn sb-btn-primary" onClick={() => onSave(text)}>Save note</button>
        </>
      }>
      <label className="sb-field">
        <span className="sb-group-title">Your note (private, saved in this browser)</span>
        <textarea className="sb-input sb-textarea" value={text} maxLength={NOTE_MAX_LENGTH} rows={6} onChange={(event) => setText(event.target.value)} />
      </label>
      <p className="sb-muted">{text.length}/{NOTE_MAX_LENGTH}</p>
    </Sheet>
  );
}
