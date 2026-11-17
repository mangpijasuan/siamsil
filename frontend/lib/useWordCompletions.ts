"use client";

import { useEffect, useState } from "react";

/**
 * Completions for the word being typed, fetched once typing pauses. Completion is a help,
 * not a feature the page depends on: a failed or late request just shows nothing.
 */
export function useWordCompletions(
  prefix: string | null,
  fetchWords: (prefix: string) => Promise<string[]>,
  delayMs = 150,
): string[] {
  const [result, setResult] = useState<{ prefix: string; words: string[] } | null>(null);

  useEffect(() => {
    if (!prefix) return;
    let current = true;
    const timer = setTimeout(() => {
      fetchWords(prefix)
        .then((words) => { if (current) setResult({ prefix, words }); })
        .catch(() => { if (current) setResult({ prefix, words: [] }); });
    }, delayMs);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [prefix, fetchWords, delayMs]);

  // Words fetched for an earlier prefix are never shown for the current one.
  return prefix && result?.prefix === prefix ? result.words : [];
}
