/**
 * Word completion helpers for the dictionary search and Translate. Pure functions only,
 * so they can be unit-tested without a browser.
 *
 * Completion works on the word being typed at the end of the text. It never changes
 * anything the user typed before that word, and only adds a word the user chose.
 */

// A word: letters with inner apostrophes or hyphens (ki-it, Zeisu'n), as the API counts them.
const TRAILING_WORD = /([A-Za-z]+(?:['’-][A-Za-z]*)*)$/;

export const MIN_COMPLETION_LETTERS = 2;

/** The word being typed at the end of `text`, or null when the text ends in a space or symbol. */
export function trailingWord(text: string): { start: number; word: string } | null {
  const match = TRAILING_WORD.exec(text);
  if (!match) return null;
  return { start: match.index, word: match[1] };
}

/** The partial word worth completing: at least MIN_COMPLETION_LETTERS letters long. */
export function completionPrefix(text: string): string | null {
  const current = trailingWord(text);
  return current && current.word.length >= MIN_COMPLETION_LETTERS ? current.word : null;
}

/** Replace the word being typed with the chosen word, followed by a space. */
export function completeTrailingWord(text: string, word: string): string {
  const current = trailingWord(text);
  const before = current ? text.slice(0, current.start) : text;
  return `${before}${word} `;
}

/** Suggestions worth showing: distinct, and not just the word already typed. */
export function usefulCompletions(words: string[], typed: string, limit = 5): string[] {
  const seen = new Set<string>([typed.toLowerCase()]);
  const out: string[] = [];
  for (const word of words) {
    const key = word.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(word);
    if (out.length === limit) break;
  }
  return out;
}
