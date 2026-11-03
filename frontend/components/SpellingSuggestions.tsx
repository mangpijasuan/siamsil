"use client";

import { useEffect, useRef, useState } from "react";

type Suggestion = {
  start: number;
  end: number;
  original: string;
  suggested: string;
  rule_id: string;
  mode: "replace" | "flag";
  reason: string;
};

type SpellingResult = {
  original: string;
  suggested: string;
  standard_version: string | null;
  status: "not_configured" | "no_approved_rules" | "suggestions_available";
  suggestions: Suggestion[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

/** Opt-in editor assistance. Never silently alters the parent form input. */
export default function SpellingSuggestions({
  value,
  onChange,
  enabled = true,
}: {
  value: string;
  onChange: (next: string) => void;
  enabled?: boolean;
}) {
  const [result, setResult] = useState<SpellingResult | null>(null);
  const [ignored, setIgnored] = useState(false);
  const [undoValue, setUndoValue] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const lastRequest = useRef(0);

  useEffect(() => {
    setResult(null);
    setIgnored(false);
    setError(false);
    if (!enabled || !value.trim() || value.length > 4000) return;

    const controller = new AbortController();
    const id = ++lastRequest.current;
    const timeout = setTimeout(async () => {
      try {
        const response = await fetch(`${API_URL}/api/v1/words/spelling/suggest`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: value }),
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Spelling service unavailable");
        const data = (await response.json()) as SpellingResult;
        if (id === lastRequest.current && data.original === value) setResult(data);
      } catch {
        if (!controller.signal.aborted && id === lastRequest.current) setError(true);
      }
    }, 450);

    return () => {
      clearTimeout(timeout);
      controller.abort();
      lastRequest.current += 1;
    };
  }, [enabled, value]);

  if (!enabled || !value.trim()) return null;

  const changes = result?.suggestions.filter((item) => item.mode === "replace") ?? [];
  const flags = result?.suggestions.filter((item) => item.mode === "flag") ?? [];
  const actionable = changes.length > 0 && result && result.suggested !== value && !ignored;

  return (
    <div role="region" aria-label="Zomi Standard Form spelling assistance" style={{
      padding: "8px 12px", border: "1px solid var(--border)",
      borderRadius: 10, color: "var(--text)", background: "var(--surface)",
      fontSize: 12, lineHeight: 1.5,
    }}>
      <strong>Zomi Standard Form</strong>
      {result?.standard_version && <span style={{ color: "var(--gray)", marginLeft: 6 }}>v{result.standard_version}</span>}
      {error && <p role="status" style={{ margin: "5px 0 0" }}>Spelling suggestions are temporarily unavailable. Your text is unchanged.</p>}
      {!error && result?.status === "no_approved_rules" && <p style={{ margin: "5px 0 0", color: "var(--gray)" }}>No spelling rules have been approved yet. Your text is unchanged.</p>}
      {!error && result?.status === "not_configured" && <p style={{ margin: "5px 0 0", color: "var(--gray)" }}>Standard spelling rules are not configured.</p>}
      {!error && actionable && (
        <div style={{ marginTop: 5 }}>
          <span>{changes.length} reviewed spelling suggestion{changes.length === 1 ? "" : "s"}: </span>
          <span lang="ctd" style={{ fontWeight: 600 }}>{result.suggested}</span>
          <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
            <button type="button" onClick={() => { setUndoValue(value); onChange(result.suggested); }}
              style={{ border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 8, cursor: "pointer" }}>
              Accept
            </button>
            <button type="button" onClick={() => setIgnored(true)}
              style={{ border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 8, cursor: "pointer" }}>
              Ignore
            </button>
          </div>
        </div>
      )}
      {!error && flags.length > 0 && !ignored && (
        <p style={{ margin: "5px 0 0" }}>Needs context review: {flags.map((f) => f.original).join(", ")}. No change suggested.</p>
      )}
      {undoValue !== null && (
        <button type="button" onClick={() => { onChange(undoValue); setUndoValue(null); }}
          style={{ marginTop: 6, border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 8, cursor: "pointer" }}>
          Undo last accepted correction
        </button>
      )}
    </div>
  );
}
