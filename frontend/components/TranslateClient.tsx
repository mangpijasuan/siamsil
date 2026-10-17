"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { IconArrow, IconTranslate } from "@/components/Icons";
import type { TranslateMatch } from "@/lib/api";
import { pushHistory } from "@/lib/localData";

const SOURCE_HELP: Record<string, string> = {
  dictionary: "Siamsil dictionary",
  daily_use: "Teacher-reviewed phrase",
  translation_pair: "Workbook translation pair",
  bible: "Bible ISO text",
  parallel_corpus: "Machine-translated corpus · unverified",
};

function normalizePhrase(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase().replace(/[\p{P}\p{S}]+/gu, " ").replace(/\s+/g, " ").trim();
}

type Direction = "en-zom" | "zom-en";

function isExactMatch(match: TranslateMatch, query: string, field: "english" | "zomi") {
  const needle = normalizePhrase(query);
  return Boolean(needle && normalizePhrase(match[field]) === needle);
}

function SwapIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 8h16m0 0-4-4m4 4-4 4M20 16H4m0 0 4-4m-4 4 4 4" /></svg>;
}

function CopyIcon() {
  return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></svg>;
}

export default function TranslateClient({
  query,
  direction,
  initialResults,
  note,
  error,
}: {
  query: string;
  direction: Direction;
  initialResults: TranslateMatch[];
  note?: string;
  error: string | null;
}) {
  const router = useRouter();
  const [text, setText] = useState(query);
  const [copied, setCopied] = useState(false);
  const sourceField = direction === "en-zom" ? "english" : "zomi";
  const targetField = direction === "en-zom" ? "zomi" : "english";
  const sourceLanguage = direction === "en-zom" ? "English" : "Zomi";
  const targetLanguage = direction === "en-zom" ? "Zomi" : "English";
  const showingResult = Boolean(query && normalizePhrase(text) === normalizePhrase(query));
  const exactMatches = initialResults
    .filter((match) => isExactMatch(match, query, sourceField))
    .sort((a, b) => Number(b.verified) - Number(a.verified));
  const reverseMatches = initialResults.filter((match) => isExactMatch(match, query, targetField) && !isExactMatch(match, query, sourceField));
  const relatedMatches = initialResults.filter((match) => !isExactMatch(match, query, "english") && !isExactMatch(match, query, "zomi"));
  const primary = exactMatches[0] ?? null;
  const alternates = exactMatches.slice(1);

  useEffect(() => {
    if (query) pushHistory("translate", query);
  }, [query]);

  function submit(next: string, nextDirection: Direction = direction) {
    const value = next.trim();
    const params = new URLSearchParams();
    if (value) params.set("q", value);
    if (nextDirection === "zom-en") params.set("dir", "zom-en");
    router.push(params.size ? `/zomitranslate?${params}` : "/zomitranslate");
  }

  function swap() {
    const nextDirection = direction === "en-zom" ? "zom-en" : "en-zom";
    const nextText = showingResult && primary ? primary[targetField] : text;
    setText(nextText);
    submit(nextText, nextDirection);
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* Clipboard access may be blocked. */
    }
  }

  return (
    <div className="translate-page">
      <div className="translate-container">
        <header className="translate-intro">
          <div>
            <h1 className="font-playfair">Translate</h1>
            <p>English and Zomi, side by side.</p>
          </div>
          <span className="translate-mode"><IconTranslate size={16} /> Text · stored matches</span>
        </header>

        <section className="translate-workbench" aria-label="Translation lookup">
          <div className="translate-language-bar">
            <span className="translate-language-name">{sourceLanguage}</span>
            <button type="button" className="translate-swap" onClick={swap} aria-label="Swap source and target languages" title="Swap languages"><SwapIcon /></button>
            <span className="translate-language-name translate-language-target">{targetLanguage}</span>
          </div>
          <form className="translate-panels" onSubmit={(event) => { event.preventDefault(); submit(text); }}>
            <div className="translate-input-panel">
              <label htmlFor="translate-input" className="translate-input-label">Enter {sourceLanguage} text</label>
              <textarea
                id="translate-input"
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder={`Enter ${sourceLanguage} text`}
                rows={5}
                maxLength={500}
                onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); submit(text); } }}
              />
              <div className="translate-panel-footer">
                <span>{text.length} / 500</span>
                <div className="translate-panel-actions">
                  {text && <button type="button" className="translate-clear" onClick={() => { setText(""); submit(""); }}>Clear</button>}
                  <button type="submit" className="translate-submit" disabled={!text.trim()}>Find translation <IconArrow size={15} /></button>
                </div>
              </div>
            </div>
            <div className="translate-output-panel" aria-live="polite">
              <div className="translate-output-body">
                {showingResult && primary ? (
                  <>
                    <span className="translate-output-status exact">Exact stored match</span>
                    <p className="translate-output-text">{primary[targetField]}</p>
                  </>
                ) : showingResult && error ? (
                  <div className="translate-output-state error"><strong>Could not load matches</strong><p>{error}</p></div>
                ) : showingResult && reverseMatches.length > 0 ? (
                  <div className="translate-output-state"><strong>This text matches {targetLanguage}</strong><p>Swap languages to see its {sourceLanguage} translation.</p><button type="button" onClick={swap}>Swap languages <SwapIcon /></button></div>
                ) : showingResult && relatedMatches.length > 0 ? (
                  <div className="translate-output-state"><strong>No exact stored match</strong><p>Related sentences appear below. They are examples, not a direct translation of “{query}.”</p></div>
                ) : showingResult ? (
                  <div className="translate-output-state"><strong>No stored translation yet</strong><p>Try a shorter phrase or a different spelling.</p></div>
                ) : (
                  <div className="translate-output-placeholder"><IconTranslate size={27} /><span>{query ? "Find translation to update the result" : "Translation will appear here"}</span></div>
                )}
              </div>
              <div className="translate-panel-footer translate-output-footer">
                {showingResult && primary ? (
                  <>
                    <span className="translate-output-source">{primary.label ?? SOURCE_HELP[primary.source] ?? primary.source} · <b className={primary.verified ? "reviewed" : ""}>{primary.verified ? "Reviewed" : "Not reviewed"}</b></span>
                    <button type="button" className="translate-copy" onClick={() => copy(primary[targetField])} aria-label={`Copy ${targetLanguage} translation`}><CopyIcon /> {copied ? "Copied" : "Copy"}</button>
                  </>
                ) : <span>Stored entries only · no new translation generated</span>}
              </div>
            </div>
          </form>
        </section>
        <p className="translate-trust-note">{showingResult && note ? note : "Siamsil searches existing entries. It does not create a new translation for unmatched text."}</p>

        {showingResult && alternates.length > 0 && (
          <section className="translate-alternates" aria-labelledby="translate-alternates-heading">
            <div className="translate-section-heading"><span>Same phrase · different sources</span><h2 id="translate-alternates-heading" className="font-playfair">Other exact matches <small>({alternates.length})</small></h2></div>
            <div className="translate-alternate-list">
              {alternates.map((match, index) => (
                <article className="translate-alternate" key={`${match.source}-${match.id ?? index}`}>
                  <div><span className="translate-cell-label">English</span><p>{match.english}</p></div>
                  <div><span className="translate-cell-label">Zomi</span><p className="font-playfair">{match.zomi}</p></div>
                  <footer><span>{match.label ?? SOURCE_HELP[match.source] ?? match.source}</span><span className={match.verified ? "translate-reviewed" : ""}>{match.verified ? "Reviewed" : "Not reviewed"}</span></footer>
                </article>
              ))}
            </div>
          </section>
        )}

        {showingResult && relatedMatches.length > 0 && (
          <section className="translate-alternates" aria-labelledby="translate-related-heading">
            <div className="translate-section-heading"><span>For context, not a direct answer</span><h2 id="translate-related-heading" className="font-playfair">Related sentences <small>({relatedMatches.length})</small></h2></div>
            <div className="translate-alternate-list">
              {relatedMatches.map((match, index) => (
                <article className="translate-alternate" key={`${match.source}-${match.id ?? index}`}>
                  <div><span className="translate-cell-label">English</span><p>{match.english}</p></div>
                  <div><span className="translate-cell-label">Zomi</span><p className="font-playfair">{match.zomi}</p></div>
                  <footer>
                    <span>{match.label ?? SOURCE_HELP[match.source] ?? match.source}</span>
                    <span className={match.verified ? "translate-reviewed" : ""}>{match.verified ? "Reviewed" : "Not reviewed"}</span>
                  </footer>
                </article>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
