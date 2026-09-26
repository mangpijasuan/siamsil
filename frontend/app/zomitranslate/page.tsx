import TranslateClient from "@/components/TranslateClient";
import { searchTranslate, TranslateMatch } from "@/lib/api";

type Props = { searchParams: Promise<{ q?: string }> };

export default async function TranslatePage({ searchParams }: Props) {
  const { q } = await searchParams;
  const query = q?.trim() ?? "";
  let results: TranslateMatch[] = [];
  let note: string | undefined;
  let error: string | null = null;

  if (query) {
    try {
      const data = await searchTranslate(query);
      results = data.results;
      note = data.note;
    } catch {
      error = "Could not reach the API. Start the backend on port 8001 after building the language database.";
    }
  }

  return <TranslateClient key={query} query={query} initialResults={results} note={note} error={error} />;
}
