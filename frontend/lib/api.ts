// Server-side: prefer SIAMSIL_API_URL (e.g. Docker service name), fall back to public URL.
const SERVER_API_URL =
  process.env.SIAMSIL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8001";

const CLIENT_API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

function resolveUrl(path: string): string {
  if (typeof window === "undefined") {
    return `${SERVER_API_URL}${path}`;
  }
  return `${CLIENT_API_URL}${path}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const isServer = typeof window === "undefined";
  const response = await fetch(resolveUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...(isServer ? { next: { revalidate: 60 } } : { cache: "no-store" }),
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status} for ${path}`);
  }

  return response.json() as Promise<T>;
}

export type DictionaryEntry = {
  id: number;
  english: string;
  source_word?: string;
  part_of_speech: string | null;
  part_of_speech_full?: string | null;
  domain: string | null;
  zomi: string | null;
  definition: string | null;
  usage_notes?: string | null;
  verified: boolean;
  verification_status?: string;
  flagged?: boolean;
  source: string | null;
  confidence?: number;
  suggested_correction?: string | null;
  examples?: TranslateMatch[];
};

export type BibleVerse = {
  testament: string;
  book_id: number;
  book_english: string;
  book_zomi: string;
  chapter: number;
  verse: number;
  reference: string;
  english: string | null;
  zomi_original: string;
  zomi_iso: string;
  changes_applied: string | null;
};

export type BibleBook = {
  book_id: number;
  book_english: string;
  book_zomi: string;
  testament: string;
};

export type TranslateMatch = {
  source: string;
  english: string;
  zomi: string;
  reference?: string;
  category?: string;
  domain?: string;
  verified?: boolean;
  flagged?: boolean;
  label?: string;
  exact?: boolean;
  quality_score?: number;
  model?: string;
};

export type LearningEntry = {
  id: number;
  category: string;
  sub_category: string;
  english: string;
  zomi: string;
  notes: string | null;
  verified: boolean;
  source: string;
};

export type HealthResponse = {
  status: string;
  metadata: Record<string, unknown>;
  language?: {
    database: boolean;
    dictionary_entries: number;
    verified_dictionary: number;
    parallel_sentences: number;
  };
};

export type AskResponse = {
  mode: string;
  intent: string;
  confidence: string;
  answer: string;
  note: string;
  sources: Array<{
    type: string;
    english?: string;
    zomi?: string;
    verified?: boolean;
    source?: string;
    label?: string;
    reference?: string;
  }>;
};

export function getHealth() {
  return fetchJson<HealthResponse>("/health");
}

export function searchDictionary(
  query: string,
  options?: { letter?: string; direction?: "en-zom" | "zom-en"; limit?: number },
) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (options?.letter) params.set("letter", options.letter);
  if (options?.direction) params.set("direction", options.direction);
  params.set("limit", String(options?.limit ?? 40));
  return fetchJson<{ query: string; count: number; results: DictionaryEntry[] }>(
    `/api/v1/dictionary?${params.toString()}`,
  );
}

export function getDictionaryEntry(id: number) {
  return fetchJson<DictionaryEntry>(`/api/v1/dictionary/${id}`);
}

export function getDictionaryLetters() {
  return fetchJson<{ letters: Array<{ letter: string; count: number }> }>("/api/v1/dictionary/letters");
}

export function searchTranslate(query: string) {
  return fetchJson<{ query: string; count: number; results: TranslateMatch[]; note?: string }>(
    `/api/v1/translate/search?q=${encodeURIComponent(query)}`,
  );
}

export function getBibleBooks() {
  return fetchJson<{ count: number; books: BibleBook[] }>("/api/v1/bible/books");
}

export function getBibleChapter(bookId: number, chapter: number) {
  return fetchJson<{
    book_id: number;
    chapter: number;
    book_english: string;
    book_zomi: string;
    verse_count: number;
    verses: BibleVerse[];
  }>(`/api/v1/bible/chapter?book_id=${bookId}&chapter=${chapter}`);
}

export function searchBible(query: string) {
  return fetchJson<{ query: string; count: number; results: BibleVerse[] }>(
    `/api/v1/bible/search?q=${encodeURIComponent(query)}`,
  );
}

export function getLearningGroups() {
  return fetchJson<{ count: number; groups: Record<string, LearningEntry[]> }>(
    "/api/v1/learning/groups",
  );
}

export function getDailyVerse() {
  return fetchJson<BibleVerse>("/api/v1/bible/random");
}

export function getWordOfDay() {
  return fetchJson<DictionaryEntry>("/api/v1/dictionary/word-of-day");
}

export function askSiamsil(message: string) {
  return fetchJson<AskResponse>("/api/v1/ai/ask", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export { SERVER_API_URL as API_URL };
