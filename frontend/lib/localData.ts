"use client";

import { useEffect, useState } from "react";

const KEY = "siamsil.saved-words";

export type SavedWord = {
  id: number;
  english: string;
  zomi: string | null;
};

function readSaved(): SavedWord[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as SavedWord[]) : [];
  } catch {
    return [];
  }
}

export function useSavedWords() {
  const [saved, setSaved] = useState<SavedWord[]>([]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setSaved(readSaved()));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function persist(next: SavedWord[]) {
    setSaved(next);
    localStorage.setItem(KEY, JSON.stringify(next));
  }

  return {
    saved,
    isSaved(id: number) {
      return saved.some((item) => item.id === id);
    },
    toggle(entry: SavedWord) {
      persist(
        saved.some((item) => item.id === entry.id)
          ? saved.filter((item) => item.id !== entry.id)
          : [entry, ...saved].slice(0, 200),
      );
    },
  };
}

const HISTORY_KEY = "siamsil.search-history";

export function pushHistory(kind: "dictionary" | "translate", query: string) {
  const trimmed = query.trim();
  if (!trimmed) return;
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const current = raw ? (JSON.parse(raw) as Array<{ kind: string; query: string; at: number }>) : [];
    const next = [{ kind, query: trimmed, at: Date.now() }, ...current.filter((item) => item.query !== trimmed)].slice(0, 40);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota */
  }
}

export function readHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as Array<{ kind: string; query: string; at: number }>) : [];
  } catch {
    return [];
  }
}
