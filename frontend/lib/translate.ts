/**
 * Translation direction for Zomi Translate. Pure functions only, so they can be
 * unit-tested without a browser.
 *
 * en-zom: the user types English and reads Zomi. zom-en: the reverse.
 * Links without a direction (from before the selector existed) read as en-zom.
 */

export type Direction = "en-zom" | "zom-en";

export const DEFAULT_DIRECTION: Direction = "en-zom";

export type Language = { code: "en" | "zom"; name: string };

const ENGLISH: Language = { code: "en", name: "English" };
const ZOMI: Language = { code: "zom", name: "Zomi" };

export function parseDirection(value: string | string[] | undefined | null): Direction {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "zom-en" ? "zom-en" : DEFAULT_DIRECTION;
}

export function reverseDirection(direction: Direction): Direction {
  return direction === "en-zom" ? "zom-en" : "en-zom";
}

export function languages(direction: Direction): { source: Language; target: Language } {
  return direction === "en-zom" ? { source: ENGLISH, target: ZOMI } : { source: ZOMI, target: ENGLISH };
}

/** A stored English–Zomi pair, read in the order of the chosen direction. */
export function orientPair<T extends { english: string; zomi: string }>(
  match: T,
  direction: Direction,
): { source: string; target: string } {
  return direction === "en-zom"
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
