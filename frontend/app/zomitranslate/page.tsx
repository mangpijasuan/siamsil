import TranslateClient from "@/components/TranslateClient";
import { searchTranslate, TranslateMatch } from "@/lib/api";

type Props = { searchParams: Promise<{ q?: string; dir?: string }> };

export default async function TranslatePage({ searchParams }: Props) {
  const { q, dir } = await searchParams;
  const query = q?.trim() ?? "";
  const direction = dir === "zom-en" ? "zom-en" : "en-zom";
  let results: TranslateMatch[] = [];
  let note: string | undefined;
  let error: string | null = null;

  if (query) {
    try {
      const data = await searchTranslate(query);
      results = data.results;
      note = data.note ?? undefined;
    } catch {
      error = "Could not reach the API. Start the backend on port 8001 after building the language database.";
    }
  }

  return <TranslateClient key={`${query}:${direction}`} query={query} direction={direction} initialResults={results} note={note} error={error} />;
}
