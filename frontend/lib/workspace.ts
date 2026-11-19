// The personal workspace: everything Siamsil keeps for a person, all of it in this browser (no account yet).
// Pure functions over an injected storage, so `node --test` runs them without a browser.
// Kept free of React and of "@/" imports for the same reason.

export type StorageLike = {
  readonly length: number;
  key(index: number): string | null;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
};

/** The person's own data. "Clear" removes these; reading settings stay. */
export const DATA_KEYS = [
  "siamsil.saved-words",
  "siamsil.search-history",
  "siamsil.bible-recent",
  "siamsil.bible.saved",
  "siamsil_streak",
  "siamsil_xp",
] as const;

export type WorkspaceWord = { id: number; english: string; zomi: string | null };
export type WorkspaceSearch = { kind: "dictionary" | "translate"; query: string; at: number };
export type WorkspaceChapter = { v: string; version: string; book: number; bookName: string; chapter: number };
export type WorkspaceVerse = { version: string; book: number; chapter: number; verse: number; label: string; at: string };
export type WorkspaceNote = WorkspaceVerse & { text: string };

export type Workspace = {
  savedWords: WorkspaceWord[];
  searches: WorkspaceSearch[];
  recentChapters: WorkspaceChapter[];
  bookmarks: WorkspaceVerse[];
  notes: WorkspaceNote[];
  highlights: number;
  learning: { streak: number; xp: number };
};

export function emptyWorkspace(): Workspace {
  return { savedWords: [], searches: [], recentChapters: [], bookmarks: [], notes: [], highlights: 0,
    learning: { streak: 0, xp: 0 } };
}

function parse(storage: StorageLike, key: string): unknown {
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function list(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function values(value: unknown): Record<string, unknown>[] {
  return value && typeof value === "object" && !Array.isArray(value)
    ? Object.values(value as Record<string, unknown>).filter((item): item is Record<string, unknown> =>
      !!item && typeof item === "object")
    : [];
}

function count(storage: StorageLike, key: string): number {
  let raw: string | null = null;
  try {
    raw = storage.getItem(key);
  } catch {
    return 0;
  }
  const value = Number(raw ?? 0);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;
}

function verse(item: Record<string, unknown>, at: unknown): WorkspaceVerse | null {
  const { version, book, chapter, verse: number, label } = item;
  if (typeof version !== "string" || typeof label !== "string" || !Number.isInteger(book)
    || !Number.isInteger(chapter) || !Number.isInteger(number)) return null;
  return { version, book: book as number, chapter: chapter as number, verse: number as number, label,
    at: typeof at === "string" ? at : "" };
}

/** Everything in the workspace, read defensively: a damaged entry is skipped, never fatal. */
export function readWorkspace(storage: StorageLike): Workspace {
  const workspace = emptyWorkspace();
  for (const item of list(parse(storage, "siamsil.saved-words"))) {
    if (typeof item.id === "number" && typeof item.english === "string") {
      workspace.savedWords.push({ id: item.id, english: item.english,
        zomi: typeof item.zomi === "string" ? item.zomi : null });
    }
  }
  for (const item of list(parse(storage, "siamsil.search-history"))) {
    if ((item.kind === "dictionary" || item.kind === "translate") && typeof item.query === "string") {
      workspace.searches.push({ kind: item.kind, query: item.query, at: typeof item.at === "number" ? item.at : 0 });
    }
  }
  for (const item of list(parse(storage, "siamsil.bible-recent"))) {
    if (typeof item.v === "string" && Number.isInteger(item.book) && Number.isInteger(item.chapter)) {
      workspace.recentChapters.push({ v: item.v, version: String(item.version ?? item.v), book: item.book as number,
        bookName: String(item.bookName ?? ""), chapter: item.chapter as number });
    }
  }
  const bible = parse(storage, "siamsil.bible.saved") as Record<string, unknown> | null;
  for (const item of values(bible?.bookmarks)) {
    const found = verse(item, item.createdAt);
    if (found) workspace.bookmarks.push(found);
  }
  for (const item of values(bible?.notes)) {
    const found = verse(item, item.updatedAt);
    if (found && typeof item.text === "string" && item.text.trim()) workspace.notes.push({ ...found, text: item.text });
  }
  workspace.highlights = values(bible?.highlights).length;
  workspace.bookmarks.sort((a, b) => b.at.localeCompare(a.at));
  workspace.notes.sort((a, b) => b.at.localeCompare(a.at));
  workspace.learning = { streak: count(storage, "siamsil_streak"), xp: count(storage, "siamsil_xp") };
  return workspace;
}

export function isEmpty(workspace: Workspace): boolean {
  return !workspace.savedWords.length && !workspace.searches.length && !workspace.recentChapters.length
    && !workspace.bookmarks.length && !workspace.notes.length && !workspace.highlights
    && !workspace.learning.streak && !workspace.learning.xp;
}

/** Every Siamsil item in this browser, data and settings, as one JSON document the person can keep. */
export function exportWorkspace(storage: StorageLike, now: Date = new Date()) {
  const items: Record<string, unknown> = {};
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (!key || !(key.startsWith("siamsil.") || key.startsWith("siamsil_") || key.startsWith("siamsil-"))) continue;
    const raw = storage.getItem(key);
    try {
      items[key] = raw === null ? null : JSON.parse(raw);
    } catch {
      items[key] = raw;
    }
  }
  return {
    format: "siamsil-workspace",
    version: 1,
    exported_at: now.toISOString(),
    note: "Everything Siamsil kept in this browser. Siamsil has no copy: there are no accounts yet.",
    items: Object.fromEntries(Object.entries(items).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))),
  };
}

/** Remove the person's data (not reading settings). Returns the keys that were present. */
export function clearWorkspace(storage: StorageLike): string[] {
  const removed: string[] = [];
  for (const key of DATA_KEYS) {
    try {
      if (storage.getItem(key) !== null) removed.push(key);
      storage.removeItem(key);
    } catch {
      /* storage blocked: nothing to remove */
    }
  }
  return removed;
}

/** Remove one saved word; returns the remaining list, stored. */
export function removeSavedWord(storage: StorageLike, id: number): WorkspaceWord[] {
  const next = readWorkspace(storage).savedWords.filter((word) => word.id !== id);
  storage.setItem("siamsil.saved-words", JSON.stringify(next));
  return next;
}

/** Clear search history only. */
export function clearSearches(storage: StorageLike): void {
  storage.removeItem("siamsil.search-history");
}
