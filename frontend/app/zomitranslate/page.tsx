import TranslateClient from "@/components/TranslateClient";
import { describeApiError, searchTranslate, TranslateMatch } from "@/lib/api";
import { parseDirection } from "@/lib/translate";

type Props = { searchParams: Promise<{ q?: string; dir?: string | string[] }> };

export default async function TranslatePage({ searchParams }: Props) {
  const { q, dir } = await searchParams;
  const query = q?.trim() ?? "";
  const direction = parseDirection(dir);
  let results: TranslateMatch[] = [];
  let error: string | null = null;

  if (query) {
    try {
      const data = await searchTranslate(query, direction);
      results = data.results;
    } catch (failure) {
      error = describeApiError(failure, "Translation");
    }
  }

  // Keyed by query and direction: each lookup renders fresh, so results never mix directions.
  return (
    <TranslateClient
      key={`${direction}:${query}`}
      query={query}
      direction={direction}
      initialResults={results}
      error={error}
    />
  );
}
