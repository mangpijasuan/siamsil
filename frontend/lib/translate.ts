/**
 * Translation direction for Zomi Translate. Pure functions only, so they can be
 * unit-tested without a browser.
 *
 * en-ctd: the user types English and reads Zomi. ctd-en: the reverse. Zomi's code is ctd
 * (ISO 639-3, Tedim); links from before 2026-10-27 say zom-en, which still works.
 * Links without a direction (from before the selector existed) read as en-ctd.
 */

export type Direction = "en-ctd" | "ctd-en";

export const DEFAULT_DIRECTION: Direction = "en-ctd";

export type Language = { code: "en" | "ctd"; name: string };

const ENGLISH: Language = { code: "en", name: "English" };
const ZOMI: Language = { code: "ctd", name: "Zomi" };

export function parseDirection(value: string | string[] | undefined | null): Direction {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "ctd-en" || raw === "zom-en" ? "ctd-en" : DEFAULT_DIRECTION;
}

export function reverseDirection(direction: Direction): Direction {
  return direction === "en-ctd" ? "ctd-en" : "en-ctd";
}

export function languages(direction: Direction): { source: Language; target: Language } {
  return direction === "en-ctd" ? { source: ENGLISH, target: ZOMI } : { source: ZOMI, target: ENGLISH };
}

/** A stored English–Zomi pair, read in the order of the chosen direction. */
export function orientPair<T extends { english: string; zomi: string }>(
  match: T,
  direction: Direction,
): { source: string; target: string } {
  return direction === "en-ctd"
    ? { source: match.english, target: match.zomi }
    : { source: match.zomi, target: match.english };
}

/** URL for a lookup. The default direction is written out too, so links stay unambiguous. */
export function translateHref(query: string, direction: Direction): string {
  const value = query.trim();
  const params = new URLSearchParams();
  if (value) params.set("q", value);
  params.set("dir", direction);
  return `/zomitranslate?${params.toString()}`;
}

/**
 * Swapping languages, as in other translators: the shown translation becomes the new
 * input, so the user can check it the other way. With no translation shown, the typed
 * text stays and only the direction changes.
 */
export function swapState(
  text: string,
  direction: Direction,
  shownTarget: string | null | undefined,
): { text: string; direction: Direction } {
  const next = reverseDirection(direction);
  const target = shownTarget?.trim();
  return { text: target ? target : text, direction: next };
}
