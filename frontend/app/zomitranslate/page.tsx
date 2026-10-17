import TranslateClient from "@/components/TranslateClient";
import { describeApiError, searchTranslate, TranslateMatch } from "@/lib/api";

type Props = { searchParams: Promise<{ q?: string }> };

export default async function TranslatePage({ searchParams }: Props) {
  const { q } = await searchParams;
  const query = q?.trim() ?? "";
  let results: TranslateMatch[] = [];
  let error: string | null = null;

  if (query) {
    try {
      const data = await searchTranslate(query);
      results = data.results;
    } catch (failure) {
      error = describeApiError(failure, "Translation");
    }
  }

  return <TranslateClient key={query} query={query} initialResults={results} error={error} />;
}
