"use client";

import { useState } from "react";

/**
 * Presentational, deliberately unmounted review form.
 * The authenticated BFF must supply the case and persist the decision.
 * Never call the experimental backend directly from a browser with a bearer token.
 */
export type ReviewEntry = {
  id: string;
  revision: number;
  english: string;
  zomi: string;
  burmeseReference?: string | null;
  sourceLabel: string;
  issues?: string[];
};

export type ReviewSubmission = {
  entryId: string;
  revision: number;
  decision: "accept" | "needs_changes" | "reject";
  reason: string;
  suggestedZomi?: string;
};

export type AssistantEvidence = {
  suggestion: string;
  evidence: string[];
  warning?: string;
};

export function DictionaryReviewForm({
  entry,
  assistant,
  onAnalyze,
  onSubmit,
}: {
  entry: ReviewEntry;
  assistant?: AssistantEvidence | null;
  onAnalyze?: () => Promise<void>;
  onSubmit: (submission: ReviewSubmission) => Promise<void>;
}) {
  const [decision, setDecision] = useState<ReviewSubmission["decision"]>("accept");
  const [reason, setReason] = useState("");
  const [suggestedZomi, setSuggestedZomi] = useState(entry.zomi);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (busy) return;
    if (reason.trim().length < 5) {
      setError("Explain your decision in at least five characters.");
      return;
    }
    if (decision === "needs_changes" && !suggestedZomi.trim()) {
      setError("Enter a proposed Zomi correction.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSubmit({
        entryId: entry.id,
        revision: entry.revision,
        decision,
        reason: reason.trim(),
        ...(decision === "needs_changes" ? { suggestedZomi: suggestedZomi.trim() } : {}),
      });
    } catch {
      setError("The review was not saved. Please retry or refresh your assignment.");
    } finally {
      setBusy(false);
    }
  }

  async function analyze() {
    if (!onAnalyze || busy) return;
    setBusy(true);
    setError("");
    try {
      await onAnalyze();
    } catch {
      setError("AI analysis is unavailable. You can still review the entry manually.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Dictionary human verification" className="mx-auto max-w-3xl space-y-5 rounded-xl border p-5">
      <header>
        <h2 className="text-xl font-semibold">Verify dictionary entry</h2>
        <p className="text-sm opacity-70">Source: {entry.sourceLabel} · Revision {entry.revision}</p>
      </header>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div><dt className="text-sm font-medium">English</dt><dd className="text-lg">{entry.english}</dd></div>
        <div><dt className="text-sm font-medium">Zomi (Tedim)</dt><dd className="text-lg">{entry.zomi}</dd></div>
        {entry.burmeseReference && (
          <div className="sm:col-span-2"><dt className="text-sm font-medium">Burmese (reference only)</dt><dd>{entry.burmeseReference}</dd></div>
        )}
      </dl>
      {Boolean(entry.issues?.length) && (
        <div><h3 className="font-medium">Quality flags</h3><ul className="list-inside list-disc">{entry.issues?.map((issue, i) => <li key={i}>{issue}</li>)}</ul></div>
      )}
      <div className="space-y-2 rounded-lg border p-3">
        <h3 className="font-semibold">AI Review Assistant</h3>
        <p className="text-sm">Suggestions only. AI cannot approve, reject, or publish dictionary entries.</p>
        {onAnalyze && <button type="button" disabled={busy} onClick={analyze} className="rounded border px-3 py-2 disabled:opacity-50">Analyze entry</button>}
        {assistant && (
          <div role="note" className="space-y-1 text-sm">
            <p><strong>Suggestion:</strong> {assistant.suggestion}</p>
            {assistant.warning && <p>{assistant.warning}</p>}
            <p><strong>Evidence:</strong></p>
            {assistant.evidence.length ? <ul className="list-inside list-disc">{assistant.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul> : <p>No supporting evidence supplied; verify independently.</p>}
          </div>
        )}
      </div>
      <fieldset className="space-y-2">
        <legend className="font-semibold">Human decision</legend>
        {([
          ["accept", "Correct Zomi"],
          ["needs_changes", "Needs correction"],
          ["reject", "Reject"],
        ] as const).map(([value, label]) => (
          <label key={value} className="flex items-center gap-2">
            <input type="radio" name="review-decision" value={value} checked={decision === value} onChange={() => setDecision(value)} />
            {label}
          </label>
        ))}
      </fieldset>
      {decision === "needs_changes" && (
        <label className="block space-y-1">
          <span className="font-medium">Proposed Zomi correction (not automatically applied)</span>
          <textarea value={suggestedZomi} onChange={(e) => setSuggestedZomi(e.target.value)} className="w-full rounded border p-2" rows={3} />
        </label>
      )}
      <label className="block space-y-1">
        <span className="font-medium">Reason (required)</span>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} className="w-full rounded border p-2" rows={3} maxLength={4000} />
      </label>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button type="button" disabled={busy} onClick={submit} className="rounded bg-slate-800 px-4 py-2 text-white disabled:opacity-50">
        {busy ? "Saving…" : "Submit for independent approval"}
      </button>
      <p className="text-xs opacity-70">Submitting does not publish or approve this entry. A separate authorized editor/administrator must finalize it.</p>
    </section>
  );
}
