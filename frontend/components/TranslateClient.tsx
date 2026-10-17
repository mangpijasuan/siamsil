"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { TranslateMatch } from "@/lib/api";
import { pushHistory, useRecentSearches } from "@/lib/localData";

const MAX_LENGTH = 500;
const VISIBLE_ALTERNATES = 5;
const EXAMPLES = ["water", "thank you", "good morning", "family", "school"];

const SOURCE_LABEL: Record<string, string> = {
  dictionary: "Dictionary",
  daily_use: "Teacher-reviewed phrase",
  translation_pair: "Workbook pair",
  bible: "Bible",
  parallel_corpus: "Corpus example",
};

function sourceLabel(match: TranslateMatch) {
  return SOURCE_LABEL[match.source] ?? match.label ?? match.source;
}

function IconSwap() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7 4 3 8l4 4" /><path d="M3 8h13" /><path d="m17 20 4-4-4-4" /><path d="M21 16H8" />
    </svg>
  );
}
function IconCopy() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}
function IconInfo() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
    </svg>
  );
}
function IconClose() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function StatusChip({ verified }: { verified?: boolean }) {
  return verified
    ? <span className="tr-chip tr-chip-verified">Verified</span>
    : <span className="tr-chip tr-chip-unverified">Unverified</span>;
}

export default function TranslateClient({
  query,
  initialResults,
  error,
}: {
  query: string;
  initialResults: TranslateMatch[];
  error: string | null;
}) {
  const router = useRouter();
  const [text, setText] = useState(query);
  const [copied, setCopied] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [pending, startTransition] = useTransition();
  const recent = useRecentSearches("translate");

  useEffect(() => {
    if (query) pushHistory("translate", query);
  }, [query]);

  const primary = initialResults[0] ?? null;
  const alternates = initialResults.slice(1);
  const shownAlternates = showAll ? alternates : alternates.slice(0, VISIBLE_ALTERNATES);

  function submit(next: string) {
    const value = next.trim();
    startTransition(() => {
      router.push(value ? `/zomitranslate?q=${encodeURIComponent(value)}` : "/zomitranslate");
    });
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

  return (
    <div className="tr-root">
      <header className="tr-header">
        <p className="gold-label" style={{ marginBottom: 6 }}>Siamsil</p>
        <h1 className="font-playfair tr-h1">Zomi Translate</h1>
        <div className="tr-langs" aria-hidden="true">
          <span>English</span>
          <IconSwap />
          <span>Zomi</span>
        </div>

        <form
          className="tr-input-card"
          onSubmit={(event) => {
            event.preventDefault();
            submit(text);
          }}
        >
          <textarea
            className="tr-input"
            value={text}
            maxLength={MAX_LENGTH}
            rows={3}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit(text);
              }
            }}
            placeholder="Type English or Zomi…"
            aria-label="Text to look up"
            autoFocus={!query}
          />
          <div className="tr-input-bar">
            <span className="tr-count">{text.length}/{MAX_LENGTH}</span>
            {text && (
              <button type="button" className="tr-clear" onClick={() => { setText(""); submit(""); }} aria-label="Clear">
                <IconClose />
              </button>
            )}
            <button type="submit" className="tr-submit" disabled={!text.trim() || pending}>
              {pending ? "Looking up…" : "Translate"}
            </button>
          </div>
        </form>
      </header>

      <div className="tr-body">
        <div className="tr-notice">
          <IconInfo />
          <p>
            Siamsil shows translations it already has. It never makes one up.
            Corpus examples are machine-translated and not yet checked by people.
          </p>
        </div>

        {error && <div className="tr-error" role="alert">{error}</div>}

        {primary && (
          <section className={`tr-result${pending ? " is-pending" : ""}`} aria-label="Best match">
            <div className="tr-result-side">
              <div className="tr-side-label">English</div>
              <p className="tr-result-en">{primary.english}</p>
            </div>
            <div className="tr-result-side tr-result-zomi-side">
              <div className="tr-side-label">Zomi</div>
              <p className="font-playfair tr-result-zomi">{primary.zomi}</p>
              {primary.reference && <p className="tr-reference">{primary.reference}</p>}
            </div>
            <div className="tr-result-meta">
              <span className="tr-chip">{sourceLabel(primary)}</span>
              <StatusChip verified={primary.verified} />
              <div className="tr-actions">
                <button type="button" className="tr-action" onClick={() => copy(primary.zomi)}>
                  <IconCopy /> {copied ? "Copied" : "Copy"}
                </button>
                <button type="button" className="tr-action" onClick={() => { setText(primary.zomi); submit(primary.zomi); }}>
                  <IconSwap /> Look up Zomi
                </button>
              </div>
            </div>
          </section>
        )}

        {!error && query && !primary && (
          <div className="tr-empty">
            <p className="font-playfair tr-empty-title">No stored match for &ldquo;{query}&rdquo;</p>
            <p className="tr-empty-text">Try a single word, check the spelling, or search the dictionary.</p>
            <Link className="tr-link" href={`/zomidictionary?q=${encodeURIComponent(query)}`}>Search the dictionary →</Link>
          </div>
        )}

        {alternates.length > 0 && (
          <section aria-label="Other matches">
            <div className="word-section-label">Other matches ({alternates.length})</div>
            <ul className="tr-alt-list">
              {shownAlternates.map((match, index) => (
                <li key={`${match.source}-${match.id ?? index}`} className="tr-alt">
                  <div className="tr-alt-chips">
                    <span className="tr-chip">{sourceLabel(match)}</span>
                    <StatusChip verified={match.verified} />
                  </div>
                  <p className="tr-alt-en">{match.english}</p>
                  <p className="tr-alt-zomi">{match.zomi}</p>
                  {match.reference && <p className="tr-reference">{match.reference}</p>}
                </li>
              ))}
            </ul>
            {alternates.length > VISIBLE_ALTERNATES && (
              <button type="button" className="tr-more" onClick={() => setShowAll((value) => !value)}>
                {showAll ? "Show fewer" : `Show ${alternates.length - VISIBLE_ALTERNATES} more`}
              </button>
            )}
          </section>
        )}

        {!query && (
          <div className="tr-start">
            <p className="font-playfair tr-empty-title">Look up English and Zomi</p>
            <p className="tr-empty-text">
              Results come from the dictionary, teacher-reviewed phrases, the Bible, then corpus examples.
            </p>
            {recent.length > 0 && (
              <>
                <div className="word-section-label">Recent</div>
                <div className="tr-suggestions">
                  {recent.map((item) => (
                    <button key={item} type="button" className="tr-suggestion" onClick={() => { setText(item); submit(item); }}>{item}</button>
                  ))}
                </div>
              </>
            )}
            <div className="word-section-label">Try</div>
            <div className="tr-suggestions">
              {EXAMPLES.map((item) => (
                <button key={item} type="button" className="tr-suggestion" onClick={() => { setText(item); submit(item); }}>{item}</button>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="screen-pad" />
    </div>
  );
}
