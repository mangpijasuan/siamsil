// Pure helpers for Bible references, navigation and verse alignment.
// Kept free of React and of "@/" imports so `node --test` can run them directly.

export type BookLike = { book_id: number; name: string; name_local?: string | null; chapters: number[] };
export type VerseLike = { verse: number; label: string; text: string };
export type VersionLike = { id: string; abbreviation: string; language_iso?: string | null };

export type ChapterRef = { book: number; chapter: number };

export type ReaderParams = {
  v: string;
  compare?: string | null;
  book?: number;
  chapter?: number;
  testament?: string;
};

/** Value of `compare` that means "no second version", so a link can turn bilingual reading off. */
export const NO_COMPARE = "none";

/** Build a /bible URL. Unknown params are dropped; `compare: null` omits it. */
export function bibleHref(params: ReaderParams, verse?: number) {
  const query = new URLSearchParams({ v: params.v });
  if (params.compare) query.set("compare", params.compare);
  if (params.book) query.set("book", String(params.book));
  if (params.chapter) query.set("chapter", String(params.chapter));
  if (params.testament) query.set("testament", params.testament);
  return `/bible?${query.toString()}${verse ? `#v${verse}` : ""}`;
}

/** The version's own book name when it has one (TDB: Piancilna), else the English name. */
export function bookLabel(book: { name: string; name_local?: string | null }) {
  return book.name_local || book.name;
}

/** "Piancilna 1:3" or "Piancilna 1:3-4" for a verse label like "3-4". */
export function formatReference(bookName: string, chapter: number, verseLabel?: string | number) {
  return verseLabel === undefined || verseLabel === "" ? `${bookName} ${chapter}` : `${bookName} ${chapter}:${verseLabel}`;
}

/** Stable key for anything saved against one verse of one version. */
export function verseKey(version: string, book: number, chapter: number, verse: number) {
  return `${version}:${book}:${chapter}:${verse}`;
}

/** Previous and next chapter in canonical order, crossing into the neighbouring book; null at either end. */
export function adjacentChapters(books: BookLike[], book: number, chapter: number): { previous: ChapterRef | null; next: ChapterRef | null } {
  const index = books.findIndex((item) => item.book_id === book);
  if (index < 0) return { previous: null, next: null };
  const current = books[index];
  const position = current.chapters.indexOf(chapter);
  if (position < 0) return { previous: null, next: null };

  let previous: ChapterRef | null = null;
  if (position > 0) previous = { book, chapter: current.chapters[position - 1] };
  else {
    for (let i = index - 1; i >= 0 && !previous; i -= 1) {
      const chapters = books[i].chapters;
      if (chapters.length) previous = { book: books[i].book_id, chapter: chapters[chapters.length - 1] };
    }
  }

  let next: ChapterRef | null = null;
  if (position < current.chapters.length - 1) next = { book, chapter: current.chapters[position + 1] };
  else {
    for (let i = index + 1; i < books.length && !next; i += 1) {
      const chapters = books[i].chapters;
      if (chapters.length) next = { book: books[i].book_id, chapter: chapters[0] };
    }
  }
  return { previous, next };
}

export type AlignedVerse = { verse: number; label: string; primary: VerseLike[]; secondary: VerseLike[] };

/** Verses a label covers: "17-18" → [17, 18]; anything else → [verse, verse]. */
export function verseSpan(item: VerseLike): [number, number] {
  const match = /^(\d+)\s*[-–]\s*(\d+)$/.exec(item.label.trim());
  if (match) {
    const start = Number(match[1]);
    const end = Number(match[2]);
    if (end >= start) return [start, end];
  }
  return [item.verse, item.verse];
}

/**
 * One row per verse, in order, pairing the two versions. When a version joins verses
 * (TDB prints Genesis 1:17-18 as one verse), the other version's matching verses share that row.
 * A side with nothing for the row is an empty list; text is never altered or invented.
 */
export function alignVerses(primary: VerseLike[], secondary: VerseLike[] | null): AlignedVerse[] {
  type Item = { side: "primary" | "secondary"; start: number; end: number; verse: VerseLike };
  const items: Item[] = [
    ...primary.map((verse) => ({ side: "primary" as const, verse, ...spanOf(verse) })),
    ...(secondary ?? []).map((verse) => ({ side: "secondary" as const, verse, ...spanOf(verse) })),
  ].sort((a, b) => a.start - b.start || a.end - b.end || (a.side === "primary" ? -1 : 1));

  const rows: Array<{ start: number; end: number; primary: VerseLike[]; secondary: VerseLike[] }> = [];
  for (const item of items) {
    const last = rows[rows.length - 1];
    if (last && item.start <= last.end) {
      last.end = Math.max(last.end, item.end);
      last[item.side].push(item.verse);
    } else {
      rows.push({ start: item.start, end: item.end, primary: item.side === "primary" ? [item.verse] : [], secondary: item.side === "secondary" ? [item.verse] : [] });
    }
  }
  return rows.map((row) => ({
    verse: row.start,
    label: row.end > row.start ? `${row.start}-${row.end}` : String(row.start),
    primary: row.primary,
    secondary: row.secondary,
  }));
}

function spanOf(verse: VerseLike) {
  const [start, end] = verseSpan(verse);
  return { start, end };
}

/**
 * Which version to show beside the main one. An explicit `compare` wins ("none" turns it off);
 * otherwise a non-English main version is paired with English (WEB first), so bilingual reading is the default.
 */
export function chooseCompanion<V extends VersionLike>(versions: V[], main: V, requested: string | undefined): V | null {
  if (requested === NO_COMPARE) return null;
  if (requested) return versions.find((item) => item.id === requested && item.id !== main.id) ?? null;
  if (main.language_iso === "eng") return null;
  const english = versions.filter((item) => item.language_iso === "eng" && item.id !== main.id);
  return english.find((item) => item.id === "web") ?? english[0] ?? null;
}

/** Books whose local or English name, or code, starts with or contains the query (case- and accent-insensitive). */
export function filterBooks<B extends BookLike & { code?: string }>(books: B[], query: string): B[] {
  const fold = (value: string) => value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
  const needle = fold(query);
  if (!needle) return books;
  return books.filter((book) =>
    [book.name_local ?? "", book.name, book.code ?? ""].some((name) => fold(name).includes(needle)),
  );
}
