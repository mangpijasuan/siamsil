// Bookmarks, highlights and notes kept on this device only (no account sync yet).
// Pure functions over plain objects; the storage adapter is injected so tests need no browser.

export type HighlightColor = "gold" | "green" | "blue" | "rose";
export const HIGHLIGHT_COLORS: HighlightColor[] = ["gold", "green", "blue", "rose"];

export type VerseRef = {
  version: string;
  book: number;
  chapter: number;
  verse: number;
  /** Human reference at save time, e.g. "Piancilna 1:3", so lists need no extra lookups. */
  label: string;
};

export type Bookmark = VerseRef & { createdAt: string };
export type Highlight = VerseRef & { color: HighlightColor; updatedAt: string };
export type Note = VerseRef & { text: string; createdAt: string; updatedAt: string };

export type SavedData = {
  schema: 1;
  bookmarks: Record<string, Bookmark>;
  highlights: Record<string, Highlight>;
  notes: Record<string, Note>;
};

export const SAVED_DATA_KEY = "siamsil.bible.saved";
export const NOTE_MAX_LENGTH = 4000;

export function emptySavedData(): SavedData {
  return { schema: 1, bookmarks: {}, highlights: {}, notes: {} };
}

export function refKey(ref: Pick<VerseRef, "version" | "book" | "chapter" | "verse">) {
  return `${ref.version}:${ref.book}:${ref.chapter}:${ref.verse}`;
}

function isRef(value: unknown): value is VerseRef {
  const item = value as VerseRef;
  return !!item && typeof item.version === "string" && Number.isInteger(item.book) && Number.isInteger(item.chapter)
    && Number.isInteger(item.verse) && typeof item.label === "string";
}

/** Parse stored JSON defensively: drop malformed entries instead of failing the whole store. */
export function parseSavedData(raw: string | null): SavedData {
  const data = emptySavedData();
  if (!raw) return data;
  let parsed: Partial<SavedData>;
  try {
    parsed = JSON.parse(raw) as Partial<SavedData>;
  } catch {
    return data;
  }
  for (const item of Object.values(parsed.bookmarks ?? {})) {
    if (isRef(item) && typeof item.createdAt === "string") data.bookmarks[refKey(item)] = item;
  }
  for (const item of Object.values(parsed.highlights ?? {})) {
    if (isRef(item) && HIGHLIGHT_COLORS.includes(item.color)) data.highlights[refKey(item)] = item;
  }
  for (const item of Object.values(parsed.notes ?? {})) {
    if (isRef(item) && typeof item.text === "string" && item.text.trim()) data.notes[refKey(item)] = item;
  }
  return data;
}

function copyRef(ref: VerseRef): VerseRef {
  return { version: ref.version, book: ref.book, chapter: ref.chapter, verse: ref.verse, label: ref.label };
}

/** Add a bookmark, or remove it when the verse is already bookmarked. One bookmark per verse. */
export function toggleBookmark(data: SavedData, ref: VerseRef, now: string): SavedData {
  const key = refKey(ref);
  const bookmarks = { ...data.bookmarks };
  if (bookmarks[key]) delete bookmarks[key];
  else bookmarks[key] = { ...copyRef(ref), createdAt: now };
  return { ...data, bookmarks };
}

/** Set a highlight colour; null (or the verse's current colour) removes it. */
export function setHighlight(data: SavedData, ref: VerseRef, color: HighlightColor | null, now: string): SavedData {
  const key = refKey(ref);
  const highlights = { ...data.highlights };
  if (!color || highlights[key]?.color === color) delete highlights[key];
  else highlights[key] = { ...copyRef(ref), color, updatedAt: now };
  return { ...data, highlights };
}

/** Save a plain-text note (trimmed, length-limited); an empty note deletes it. */
export function saveNote(data: SavedData, ref: VerseRef, text: string, now: string): SavedData {
  const key = refKey(ref);
  const notes = { ...data.notes };
  const clean = text.replace(/\r\n/g, "\n").trim().slice(0, NOTE_MAX_LENGTH);
  if (!clean) delete notes[key];
  else notes[key] = { ...copyRef(ref), text: clean, createdAt: notes[key]?.createdAt ?? now, updatedAt: now };
  return { ...data, notes };
}

/** Newest first. */
export function sortedByDate<T extends { createdAt?: string; updatedAt?: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => (b.updatedAt ?? b.createdAt ?? "").localeCompare(a.updatedAt ?? a.createdAt ?? ""));
}

/** Text placed on the clipboard or in a share sheet: the verse, its reference and the version. */
export function shareText(text: string, reference: string, versionLabel: string) {
  return `${text}\n— ${reference} (${versionLabel})`;
}
