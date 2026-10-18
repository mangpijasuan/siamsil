"use client";

import { useCallback, useLayoutEffect, useSyncExternalStore } from "react";
import { DEFAULT_PREFERENCES, normalizePreferences, PREFERENCES_KEY, resolveTheme } from "./preferences";
import type { ReadingPreferences } from "./preferences";
import { emptySavedData, parseSavedData, SAVED_DATA_KEY } from "./savedData";
import type { SavedData } from "./savedData";

// ── Reading preferences ────────────────────────────────────────────────

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** Mirror preferences onto <html> (the same attributes the boot script sets before paint). */
function applyPreferences(prefs: ReadingPreferences) {
  const root = document.documentElement;
  const theme = resolveTheme(prefs.theme, window.matchMedia?.(DARK_QUERY).matches ?? false);
  root.setAttribute("data-bible-theme", theme);
  root.setAttribute("data-bible-mode", prefs.mode);
  root.setAttribute("data-bible-face", prefs.typeface);
  root.style.setProperty("--sb-font-size", `${prefs.fontSize}px`);
  root.style.setProperty("--sb-line-height", String(prefs.lineHeight));
}

const PREFERENCES_EVENT = "siamsil:bible-preferences";
let prefsRaw: string | null | undefined;
let prefsCache: ReadingPreferences = DEFAULT_PREFERENCES;

function readPreferences(): ReadingPreferences {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(PREFERENCES_KEY);
  } catch {
    /* storage blocked: defaults */
  }
  if (raw !== prefsRaw) {
    prefsRaw = raw;
    try {
      prefsCache = normalizePreferences(JSON.parse(raw ?? "null"));
    } catch {
      prefsCache = DEFAULT_PREFERENCES;
    }
  }
  return prefsCache;
}

function subscribePreferences(listener: () => void) {
  const media = window.matchMedia?.(DARK_QUERY);
  const onStorage = (event: StorageEvent) => {
    if (event.key === PREFERENCES_KEY) listener();
  };
  media?.addEventListener("change", listener);
  window.addEventListener(PREFERENCES_EVENT, listener);
  window.addEventListener("storage", onStorage);
  return () => {
    media?.removeEventListener("change", listener);
    window.removeEventListener(PREFERENCES_EVENT, listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useReadingPreferences() {
  const prefs = useSyncExternalStore(subscribePreferences, readPreferences, () => DEFAULT_PREFERENCES);

  // Keep <html> in step (also after client-side navigation, where the boot script does not run again).
  useLayoutEffect(() => {
    applyPreferences(prefs);
  }, [prefs]);

  const update = useCallback((change: Partial<ReadingPreferences>) => {
    const next = normalizePreferences({ ...readPreferences(), ...change });
    try {
      localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
    } catch {
      /* private mode or blocked storage: apply for this visit only */
      prefsRaw = JSON.stringify(next);
      prefsCache = next;
    }
    applyPreferences(next);
    window.dispatchEvent(new Event(PREFERENCES_EVENT));
  }, []);

  return { prefs, update };
}

// ── Saved bookmarks, highlights and notes (this device only) ───────────

const EMPTY: SavedData = emptySavedData();
let cache: SavedData | null = null;
const listeners = new Set<() => void>();

function snapshot(): SavedData {
  if (!cache) {
    try {
      cache = parseSavedData(localStorage.getItem(SAVED_DATA_KEY));
    } catch {
      cache = emptySavedData();
    }
  }
  return cache;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === SAVED_DATA_KEY) {
      cache = null;
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Saved data shared by every component on the page and kept in step with other tabs. */
export function useSavedData() {
  const data = useSyncExternalStore(subscribe, snapshot, () => EMPTY);
  /** Apply a change; false when the browser refused to store it (quota, private mode). */
  const update = useCallback((change: (current: SavedData) => SavedData): boolean => {
    const next = change(snapshot());
    try {
      localStorage.setItem(SAVED_DATA_KEY, JSON.stringify(next));
    } catch {
      return false;
    }
    cache = next;
    listeners.forEach((listener) => listener());
    return true;
  }, []);
  return { data, update };
}
