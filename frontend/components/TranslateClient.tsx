"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { TranslateMatch } from "@/lib/api";
import { pushHistory } from "@/lib/localData";

const SOURCE_HELP: Record<string, string> = {
  dictionary: "From the Siamsil dictionary",
  daily_use: "Teacher-reviewed daily phrase",
  translation_pair: "Workbook translation pair",
  bible: "Bible ISO text",
  parallel_corpus: "Machine-translated corpus example — unverified",
};

export default function TranslateClient({
  query,
  initialResults,
  note,
  error,
}: {
  query: string;
  initialResults: TranslateMatch[];
  note?: string;
  error: string | null;
}) {
  const router = useRouter();
  const [text, setText] = useState(query);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (query) pushHistory("translate", query);
  }, [query]);

  const primary = initialResults[0] ?? null;
  const alternates = initialResults.slice(1);

  function submit(next: string) {
    const value = next.trim();
    if (!value) {
      router.push("/zomitranslate");
      return;
    }
    router.push(`/zomitranslate?q=${encodeURIComponent(value)}`);
  }

  function swap() {
    if (primary?.zomi) submit(primary.zomi);
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked */
    }
  }

  const warning = useMemo(
    () => note ?? "Corpus matches are machine-translated and not human-verified.",
    [note],
  );

  return (
    <>
      <header className="page-header-compact">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
          <span className="font-playfair" style={{ color: "var(--white)", fontSize: 18, fontWeight: 700 }}>Zomi Translate</span>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit(text);
          }}
          className="search-bar-navy"
        >
          <button type="button" onClick={swap} aria-label="Swap using top result" style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer" }}>
            ⇄
          </button>
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            type="search"
            placeholder="English or Zomi text…"
            autoFocus
          />
        </form>
      </header>

      <p style={{ margin: "12px 16px 0", fontSize: 12, color: "var(--gray)", lineHeight: 1.5 }}>
        Retrieval only — Siamsil does not generate new translations yet. {warning}
      </p>

      {primary && (
        <div style={{ margin: "16px 16px 0", background: "var(--white)", borderRadius: 16, overflow: "hidden", boxShadow: "0 4px 20px rgba(27,42,74,0.1)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
            <div style={{ padding: "20px 18px", borderRight: "1px solid var(--gray2)" }}>
              <div className="gold-label" style={{ marginBottom: 6 }}>English</div>
              <p style={{ fontSize: 15, color: "var(--navy)", lineHeight: 1.5, margin: 0 }}>{primary.english}</p>
            </div>
            <div style={{ padding: "20px 18px", background: "rgba(201,168,76,0.06)" }}>
              <div className="gold-label" style={{ marginBottom: 6 }}>Zomi</div>
              <p className="font-playfair" style={{ fontSize: 18, color: "var(--navy)", lineHeight: 1.4, margin: 0 }}>{primary.zomi}</p>
              <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: 9, background: "var(--cream)", color: "var(--gray)", padding: "3px 8px", borderRadius: 20, fontWeight: 600 }}>
                  {primary.label ?? SOURCE_HELP[primary.source] ?? primary.source}
                </span>
                {primary.verified ? (
                  <span style={{ fontSize: 9, color: "#15803d", fontWeight: 700 }}>Verified</span>
                ) : (
                  <span style={{ fontSize: 9, color: "#b45309", fontWeight: 700 }}>Unverified</span>
                )}
                <button
                  type="button"
                  onClick={() => copy(primary.zomi)}
                  style={{ marginLeft: "auto", border: "1px solid var(--border)", background: "var(--white)", borderRadius: 8, padding: "4px 8px", fontSize: 11, cursor: "pointer" }}
                >
                  {copied ? "Copied" : "Copy Zomi"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div style={{ margin: "16px 16px 0", padding: "12px 16px", borderRadius: 12, background: "#FEE2E2", color: "#B91C1C", fontSize: 13 }}>{error}</div>
      )}

      {!error && query && initialResults.length === 0 && (
        <div style={{ padding: "48px 20px", textAlign: "center" }}>
          <p className="font-playfair" style={{ fontSize: 16, fontWeight: 600, color: "var(--navy)" }}>No stored match for “{query}”</p>
          <p style={{ fontSize: 13, color: "var(--gray)", marginTop: 8 }}>Siamsil will not invent a translation.</p>
        </div>
      )}

      {alternates.length > 0 && (
        <div style={{ padding: "0 16px" }}>
          <div className="word-section-label">Other matches ({alternates.length})</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {alternates.map((match, i) => (
              <div key={`${match.source}-${i}`} style={{ background: "var(--white)", borderRadius: 12, overflow: "hidden", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
                <div style={{ padding: "12px 14px", borderRight: "1px solid var(--gray2)" }}>
                  <div style={{ fontSize: 9, fontWeight: 600, background: "var(--cream)", color: "var(--gray)", display: "inline-block", padding: "2px 7px", borderRadius: 20, marginBottom: 6 }}>
                    {match.label ?? match.source}
                  </div>
                  <p style={{ fontSize: 13, color: "var(--navy)", lineHeight: 1.5, margin: 0 }}>{match.english}</p>
                </div>
                <div style={{ padding: "12px 14px" }}>
                  <p style={{ fontSize: 13, color: "var(--navy)", lineHeight: 1.5, margin: 0 }}>{match.zomi}</p>
                  {match.reference && <p style={{ fontSize: 10, color: "var(--gray)", marginTop: 4 }}>{match.reference}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!query && (
        <div style={{ padding: "48px 20px", textAlign: "center" }}>
          <p className="font-playfair" style={{ fontSize: 16, fontWeight: 600, color: "var(--navy)" }}>Look up stored English ↔ Zomi pairs</p>
          <p style={{ fontSize: 13, color: "var(--gray)", marginTop: 6 }}>Dictionary, reviewed phrases, Bible, then unverified corpus examples</p>
        </div>
      )}

      <div className="screen-pad" />
    </>
  );
}
