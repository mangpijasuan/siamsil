import createClient from "openapi-fetch";

import type { components, paths } from "@/lib/generated/api-types";

// Server-side requests use the private service URL; browser requests use the
// public URL baked into the client bundle by Next.js.
const SERVER_API_URL =
  process.env.SIAMSIL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8001";

const CLIENT_API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

const configuredTimeout = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS ?? 10_000);
const API_TIMEOUT_MS = Number.isFinite(configuredTimeout) && configuredTimeout > 0
  ? configuredTimeout
  : 10_000;

type ErrorDetail = {
  location?: string[];
  message?: string;
  type?: string;
};

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string | null;
    details?: ErrorDetail[];
  };
};

type ApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;
  readonly details?: ErrorDetail[];

  constructor(options: {
    message: string;
    status: number;
    code: string;
    requestId?: string;
    details?: ErrorDetail[];
    cause?: unknown;
  }) {
    super(options.message, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId;
    this.details = options.details;
  }
}

function resolveBaseUrl(): string {
  return typeof window === "undefined" ? SERVER_API_URL : CLIENT_API_URL;
}

async function fetchWithPolicy(request: Request): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => {
    controller.abort(new DOMException("Siamsil API request timed out", "TimeoutError"));
  }, API_TIMEOUT_MS);
  const forwardAbort = () => controller.abort(request.signal.reason);
  request.signal.addEventListener("abort", forwardAbort, { once: true });

  try {
    if (typeof window === "undefined" && request.method === "GET") {
      return await fetch(request, {
        signal: controller.signal,
        next: { revalidate: 60 },
      });
    }
    return await fetch(request, {
      cache: "no-store",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
    request.signal.removeEventListener("abort", forwardAbort);
  }
}

function apiClient(accessToken?: string) {
  return createClient<paths>({
    baseUrl: resolveBaseUrl(),
    fetch: fetchWithPolicy,
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
}

function errorEnvelope(value: unknown): ErrorEnvelope | undefined {
  if (!value || typeof value !== "object") return undefined;
  return value as ErrorEnvelope;
}

async function expectData<T>(request: Promise<ApiResult<T>>, path: string): Promise<T> {
  try {
    const result = await request;
    if (result.data !== undefined) return result.data;

    const envelope = errorEnvelope(result.error);
    const error = envelope?.error;
    throw new ApiError({
      message: error?.message ?? `Siamsil API request failed for ${path}.`,
      status: result.response.status,
      code: error?.code ?? `http_${result.response.status}`,
      requestId: error?.request_id ?? undefined,
      details: error?.details,
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    throw new ApiError({
      message: timedOut
        ? "The Siamsil service took too long to respond."
        : "The Siamsil service could not be reached.",
      status: timedOut ? 408 : 0,
      code: timedOut ? "request_timeout" : "network_error",
      cause: error,
    });
  }
}

export type DictionaryEntry = components["schemas"]["DictionaryEntry"];
export type BibleVerse = components["schemas"]["BibleVerse"];
export type BibleBook = components["schemas"]["BibleBook"];
export type TranslateMatch = components["schemas"]["TranslateMatch"];
export type LearningEntry = components["schemas"]["LearningEntry"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type AskResponse = components["schemas"]["AskResponse"];
export type IdentityResponse = components["schemas"]["IdentityResponse"];
export type RoleName = components["schemas"]["RoleName"];

type DictionarySearchResponse = components["schemas"]["DictionarySearchResponse"];
type DictionaryLettersResponse = components["schemas"]["DictionaryLettersResponse"];
type TranslationSearchResponse = components["schemas"]["TranslationSearchResponse"];
type BibleBooksResponse = components["schemas"]["BibleBooksResponse"];
type BibleChapterResponse = components["schemas"]["BibleChapterResponse"];
type BibleSearchResponse = components["schemas"]["BibleSearchResponse"];
type LearningGroupsResponse = components["schemas"]["LearningGroupsResponse"];
type RoleAssignmentResponse = components["schemas"]["RoleAssignmentResponse"];

export function getHealth(): Promise<HealthResponse> {
  return expectData(apiClient().GET("/health"), "/health");
}

export function searchDictionary(
  query: string,
  options?: { letter?: string; direction?: "en-zom" | "zom-en"; limit?: number },
): Promise<DictionarySearchResponse> {
  return expectData(
    apiClient().GET("/api/v1/dictionary", {
      params: {
        query: {
          q: query,
          letter: options?.letter,
          direction: options?.direction ?? "en-zom",
          limit: options?.limit ?? 40,
        },
      },
    }),
    "/api/v1/dictionary",
  );
}

export function getDictionaryEntry(id: number): Promise<DictionaryEntry> {
  return expectData(
    apiClient().GET("/api/v1/dictionary/{entry_id}", {
      params: { path: { entry_id: id } },
    }),
    "/api/v1/dictionary/{entry_id}",
  );
}

export function getDictionaryLetters(): Promise<DictionaryLettersResponse> {
  return expectData(apiClient().GET("/api/v1/dictionary/letters"), "/api/v1/dictionary/letters");
}

export function searchTranslate(query: string): Promise<TranslationSearchResponse> {
  return expectData(
    apiClient().GET("/api/v1/translate/search", {
      params: { query: { q: query } },
    }),
    "/api/v1/translate/search",
  );
}

export function getBibleBooks(): Promise<BibleBooksResponse> {
  return expectData(apiClient().GET("/api/v1/bible/books"), "/api/v1/bible/books");
}

export function getBibleChapter(bookId: number, chapter: number): Promise<BibleChapterResponse> {
  return expectData(
    apiClient().GET("/api/v1/bible/chapter", {
      params: { query: { book_id: bookId, chapter } },
    }),
    "/api/v1/bible/chapter",
  );
}

export function searchBible(query: string): Promise<BibleSearchResponse> {
  return expectData(
    apiClient().GET("/api/v1/bible/search", {
      params: { query: { q: query } },
    }),
    "/api/v1/bible/search",
  );
}

export function getLearningGroups(): Promise<LearningGroupsResponse> {
  return expectData(apiClient().GET("/api/v1/learning/groups"), "/api/v1/learning/groups");
}

export function getDailyVerse(): Promise<BibleVerse> {
  return expectData(apiClient().GET("/api/v1/bible/random"), "/api/v1/bible/random");
}

export function getWordOfDay(): Promise<DictionaryEntry> {
  return expectData(
    apiClient().GET("/api/v1/dictionary/word-of-day"),
    "/api/v1/dictionary/word-of-day",
  );
}

export function askSiamsil(message: string): Promise<AskResponse> {
  return expectData(
    apiClient().POST("/api/v1/ai/ask", { body: { message } }),
    "/api/v1/ai/ask",
  );
}

export function getCurrentIdentity(accessToken: string): Promise<IdentityResponse> {
  return expectData(
    apiClient(accessToken).GET("/api/v1/identity/me"),
    "/api/v1/identity/me",
  );
}

export function grantUserRole(
  accessToken: string,
  userId: string,
  role: RoleName,
): Promise<RoleAssignmentResponse> {
  return expectData(
    apiClient(accessToken).POST("/api/v1/identity/users/{user_id}/roles/{role}", {
      params: { path: { user_id: userId, role } },
    }),
    "/api/v1/identity/users/{user_id}/roles/{role}",
  );
}

export { SERVER_API_URL as API_URL };
