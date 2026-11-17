"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  type ExperimentalTranslation as Result,
  getExperimentalTranslationStatus,
  translateExperimental,
} from "@/lib/api";
import { type Direction, languages } from "@/lib/translate";

// Remembered per device only; off until the person turns it on.
const STORAGE_KEY = "siamsil.experimentalTranslation";
const LANG_ATTR = { en: "en", ctd: "ctd" } as const;

function readPreference(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

function writePreference(on: boolean) {
  try {
    window.localStorage.setItem(STORAGE_KEY, on ? "on" : "off");
  } catch {
    /* storage may be blocked; the switch still works for this visit */
  }
}

/** Opt-in machine translation, shown apart from Siamsil's stored translations and always labelled experimental. */
export default function ExperimentalTranslation({ query, direction }: { query: string; direction: Direction }) {
  const [available, setAvailable] = useState(false);
  const [enabled, setEnabled] = useState(false);
  // The latest answer and the request it belongs to; anything else on screen is loading.
  const [answer, setAnswer] = useState<{ key: string; result?: Result; error?: string } | null>(null);
  const shown = languages(direction);
  const key = `${direction}\n${query}`;
  const wanted = enabled && query.trim() !== "";
  const current = answer?.key === key ? answer : null;
  const loading = wanted && !current;

  useEffect(() => {
    let cancelled = false;
    getExperimentalTranslationStatus()
      .then((status) => {
        if (cancelled) return;
        setAvailable(status.available);
        setEnabled(status.available && readPreference());
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!wanted) return;
    let cancelled = false;
    translateExperimental(query, direction)
      .then((result) => {
        if (!cancelled) setAnswer({ key, result });
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        const message = reason instanceof ApiError ? reason.message : "Machine translation is not available right now.";
        setAnswer({ key, error: message });
      });
    return () => {
      cancelled = true;
    };
  }, [wanted, key, query, direction]);

  if (!available) return null;

  function toggle() {
    const next = !enabled;
    setEnabled(next);
    writePreference(next);
  }

  return (
    <section className="tr-exp" aria-label="Machine translation (experimental)">
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        className={`tr-exp-switch${enabled ? " is-on" : ""}`}
        onClick={toggle}
      >
        <span className="tr-exp-track" aria-hidden="true"><span className="tr-exp-thumb" /></span>
        Try machine translation (experimental)
      </button>

      {wanted && (
        <div className={`tr-exp-card${loading ? " is-pending" : ""}`} aria-busy={loading}>
          <div className="tr-exp-head">
            <span className="tr-chip tr-chip-experimental">Experimental</span>
            <span className="tr-side-label tr-exp-title">Machine translation · {shown.target.name}</span>
          </div>
          {loading && <p className="tr-exp-loading" role="status">Translating…</p>}
          {current?.error && <p className="tr-exp-error" role="alert">{current.error}</p>}
          {current?.result && (
            <>
              <p className="font-playfair tr-exp-text" lang={LANG_ATTR[shown.target.code]}>{current.result.translation}</p>
              <p className="tr-exp-note">{current.result.note}</p>
              <p className="tr-exp-model">
                Model: {current.result.system} ({current.result.system_version.slice(0, 10)})
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
