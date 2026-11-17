import { describeApiError, getDictionaryLetters, searchDictionary, DictionaryEntry } from "@/lib/api";
import DictionaryShell from "@/components/DictionaryShell";

type Props = { searchParams: Promise<{ q?: string; letter?: string; dir?: string }> };

export default async function DictionaryPage({ searchParams }: Props) {
  const { q, letter, dir } = await searchParams;
  const query = q?.trim() ?? "";
  const activeLetter = letter?.toUpperCase() ?? "All";
  // zom-en: links from before Zomi was labelled ctd.
  const direction = dir === "ctd-en" || dir === "zom-en" ? "ctd-en" : "en-ctd";

  let entries: DictionaryEntry[] = [];
  let letters: Array<{ letter: string; count: number }> = [];
  let error: string | null = null;

  try {
    const [letterData, searchData] = await Promise.all([
      getDictionaryLetters(),
      query || activeLetter !== "All"
        ? searchDictionary(query, {
            letter: activeLetter !== "All" ? activeLetter : undefined,
            direction,
            limit: 50,
          })
        : Promise.resolve({ results: [] as DictionaryEntry[] }),
    ]);
    letters = letterData.letters;
    entries = searchData.results;
  } catch (failure) {
    error = describeApiError(failure, "Dictionary");
  }

  return (
    <DictionaryShell
      key={`${direction}:${activeLetter}:${query}`}
      entries={entries}
      query={query}
      activeLetter={activeLetter}
      direction={direction}
      letters={letters}
      error={error}
    />
  );
}
