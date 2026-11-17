"use client";

import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  type ExperimentalTranslation as Result,
  type ExperimentalTranslationStatus,
  getExperimentalTranslationStatus,
  translateExperimental,
} from "@/lib/api";
import { type Direction, languages } from "@/lib/translate";

const LANG_ATTR = { en: "en", ctd: "ctd" } as const;

/** Opt-in machine translation, shown apart from Siamsil's stored translations and always labelled experimental. */
export default function ExperimentalTranslation({ query, direction }: { query: string; direction: Direction }) {
  const [status, setStatus] = useState<ExperimentalTranslationStatus | null>(null);
  const [answer, setAnswer] = useState<{ key: string; result?: Result; error?: string } | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const nextRequest = useRef(0);
  const shown = languages(direction);
  const key = `${direction}\n${query}`;
  const current = answer?.key === key ? answer : null;
  const loading = pendingKey === key;
  const hosted = status?.system === "OpenAI";

  useEffect(() => {
    let cancelled = false;
    getExperimentalTranslationStatus()
      .then((value) => {
        if (!cancelled) setStatus(value);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status?.available) return null;

  async function generate() {
    const request = ++nextRequest.current;
    setAnswer(null);
    setPendingKey(key);
    try {
      const result = await translateExperimental(query, direction);
      if (request === nextRequest.current) setAnswer({ key, result });
    } catch (reason: unknown) {
      const message = reason instanceof ApiError ? reason.message : "Machine translation is not available right now.";
      if (request === nextRequest.current) setAnswer({ key, error: message });
    } finally {
      if (request === nextRequest.current) setPendingKey(null);
    }
  }

  return (
    <section className="tr-exp" aria-label="Machine translation (experimental)">
      <button
        type="button"
        className="tr-exp-switch"
        disabled={loading || !query.trim()}
        aria-describedby={hosted ? "tr-exp-provider-note" : undefined}
        onClick={generate}
      >
        {current?.error ? "Try again" : "Generate translation (experimental)"}
      </button>
      {hosted && <p className="tr-exp-note" id="tr-exp-provider-note">{status.note}</p>}

      {(loading || current) && (
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
                Model: {current.result.system} ({current.result.system_version})
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
