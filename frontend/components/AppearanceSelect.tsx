"use client";

import { useEffect, useSyncExternalStore } from "react";
import {
  APPEARANCE_EVENT,
  APPEARANCE_KEY,
  DARK_QUERY,
  DEFAULT_APPEARANCE,
  normalizeAppearance,
  resolveAppearance,
} from "@/lib/appearance";
import type { Appearance } from "@/lib/appearance";

// Set only when storage is blocked (private mode): the choice then lasts for this visit.
let visitOnlyMode: Appearance | null = null;

function read(): Appearance {
  if (visitOnlyMode) return visitOnlyMode;
  try {
    return normalizeAppearance(localStorage.getItem(APPEARANCE_KEY));
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

function apply(mode: Appearance) {
  const shown = resolveAppearance(mode, window.matchMedia(DARK_QUERY).matches);
  document.documentElement.setAttribute("data-app-theme", shown);
  document.documentElement.style.colorScheme = shown;
  window.dispatchEvent(new Event(APPEARANCE_EVENT));
}

function subscribe(listener: () => void) {
  const media = window.matchMedia(DARK_QUERY);
  const onSystem = () => {
    if (read() === "system") apply("system");
  };
  window.addEventListener(APPEARANCE_EVENT, listener);
  window.addEventListener("storage", listener);
  media.addEventListener("change", onSystem);
  return () => {
    window.removeEventListener(APPEARANCE_EVENT, listener);
    window.removeEventListener("storage", listener);
    media.removeEventListener("change", onSystem);
  };
}

/** The Light / Dark / System choice. The saved mode is applied before paint by the boot script; this keeps it in step. */
export default function AppearanceSelect() {
  const mode = useSyncExternalStore(subscribe, read, () => DEFAULT_APPEARANCE);

  // After client-side navigation the boot script does not run again, so re-assert the saved mode.
  useEffect(() => {
    apply(mode);
  }, [mode]);

  return (
    <select
      className="app-theme-select"
      aria-label="Appearance"
      value={mode}
      onChange={(event) => {
        const next = normalizeAppearance(event.target.value);
        try {
          localStorage.setItem(APPEARANCE_KEY, next);
          visitOnlyMode = null;
        } catch {
          visitOnlyMode = next; // private mode or blocked storage: apply for this visit only
        }
        apply(next);
      }}
    >
      <option value="light">Light</option>
      <option value="dark">Dark</option>
      <option value="system">System</option>
    </select>
  );
}
