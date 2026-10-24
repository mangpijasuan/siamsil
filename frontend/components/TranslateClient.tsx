"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { TranslateMatch } from "@/lib/api";
import { pushHistory, useRecentSearches } from "@/lib/localData";
import { IconSwap } from "@/components/Icons";
import {
  type Direction,
  languages,
  orientPair,
  reverseDirection,
  swapState,
  translateHref,
} from "@/lib/translate";

const MAX_LENGTH = 500;
const VISIBLE_ALTERNATES = 5;
// English starters only: Siamsil never shows Zomi it does not hold, so Zomi → English has none.
const EXAMPLES = ["water", "thank you", "good morning", "family", "school"];
const LANG_ATTR = { en: "en", zom: "zom" } as const;

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
  direction,
  initialResults,
  error,
}: {
  query: string;
  /** The direction these results were looked up in (from the URL). */
  direction: Direction;
  initialResults: TranslateMatch[];
  error: string | null;
}) {
  const router = useRouter();
  const [text, setText] = useState(query);
  // The selector can run ahead of the results while a lookup loads; results and their
  // labels always use `direction`, so they never show one direction's text under the other's names.
  const [selected, setSelected] = useState<Direction>(direction);
  const [copied, setCopied] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [pending, startTransition] = useTransition();
  const recent = useRecentSearches("translate");

  useEffect(() => {
    if (query) pushHistory("translate", query);
  }, [query]);

  const primary = initialResults[0] ?? null;
  const shown = languages(direction);
  const chosen = languages(selected);
  const primarySides = primary ? orientPair(primary, direction) : null;
  const alternates = initialResults.slice(1);
  const shownAlternates = showAll ? alternates : alternates.slice(0, VISIBLE_ALTERNATES);

  function submit(next: string, nextDirection: Direction = selected) {
    startTransition(() => {
      router.push(translateHref(next, nextDirection));
    });
  }

  function swap() {
    // Offer the shown translation as the new input only while it belongs to the typed text.
    const target = primarySides && text.trim() === query && selected === direction ? primarySides.target : null;
    const next = swapState(text, selected, target);
    setSelected(next.direction);
    setText(next.text);
    submit(next.text, next.direction);
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
        <div className="tr-langs tr-langs-switch" role="group" aria-label="Translation direction">
          <span className="tr-lang" data-testid="source-language">{chosen.source.name}</span>
          <button
            type="button"
            className="tr-swap"
            onClick={swap}
            aria-label={`Swap languages. Now ${chosen.source.name} to ${chosen.target.name}`}
            title="Swap languages"
          >
            <IconSwap />
          </button>
          <span className="tr-lang" data-testid="target-language">{chosen.target.name}</span>
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
            placeholder={`Type ${chosen.source.name}…`}
            aria-label={`${chosen.source.name} text to look up`}
            lang={LANG_ATTR[chosen.source.code]}
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
            Corpus examples are machine-translated; only those marked Verified were checked by Zomi reviewers.
          </p>
        </div>

        {pending && <p className="tr-loading" role="status">Looking up {chosen.source.name} → {chosen.target.name}…</p>}

        {error && (
          <div className="tr-error" role="alert">
            {error}{" "}
            <button type="button" className="tr-retry" onClick={() => startTransition(() => router.refresh())}>
              Try again
            </button>
          </div>
        )}

        {primary && primarySides && (
          <section
            className={`tr-result${pending ? " is-pending" : ""}`}
            aria-label={`Best match, ${shown.source.name} to ${shown.target.name}`}
            aria-busy={pending}
            data-direction={direction}
          >
            {/* Source first, then the translation (the highlighted side), whichever the languages. */}
            <div className="tr-result-side">
              <div className="tr-side-label">{shown.source.name}</div>
              <p className="tr-result-en" lang={LANG_ATTR[shown.source.code]}>{primarySides.source}</p>
            </div>
            <div className="tr-result-side tr-result-zomi-side">
              <div className="tr-side-label">{shown.target.name}</div>
              <p className="font-playfair tr-result-zomi" lang={LANG_ATTR[shown.target.code]}>{primarySides.target}</p>
              {primary.reference && <p className="tr-reference">{primary.reference}</p>}
            </div>
            <div className="tr-result-meta">
              <span className="tr-chip">{sourceLabel(primary)}</span>
              <StatusChip verified={primary.verified} />
              <div className="tr-actions">
                <button type="button" className="tr-action" onClick={() => copy(primarySides.target)}>
                  <IconCopy /> {copied ? "Copied" : `Copy ${shown.target.name}`}
                </button>
              </div>
            </div>
          </section>
        )}

        {!error && query && !primary && (
          <div className={`tr-empty${pending ? " is-pending" : ""}`}>
            <p className="font-playfair tr-empty-title">
              No stored {shown.source.name} → {shown.target.name} match for &ldquo;{query}&rdquo;
            </p>
            <p className="tr-empty-text">Try a single word, check the spelling, or search the dictionary.</p>
            <p className="tr-empty-links">
              <Link className="tr-link" href={translateHref(query, reverseDirection(direction))}>
                Look it up {shown.target.name} → {shown.source.name} instead →
              </Link>
              <Link className="tr-link" href={`/zomidictionary?q=${encodeURIComponent(query)}&dir=${direction}`}>
                Search the dictionary →
              </Link>
            </p>
          </div>
        )}

        {alternates.length > 0 && (
          <section aria-label="Other matches">
            <div className="word-section-label">Other matches ({alternates.length})</div>
            <ul className="tr-alt-list">
              {shownAlternates.map((match, index) => {
                const sides = orientPair(match, direction);
                return (
                <li key={`${match.source}-${match.id ?? index}`} className="tr-alt">
                  <div className="tr-alt-chips">
                    <span className="tr-chip">{sourceLabel(match)}</span>
                    <StatusChip verified={match.verified} />
                  </div>
                  <p className="tr-alt-en" lang={LANG_ATTR[shown.source.code]}>{sides.source}</p>
                  <p className="tr-alt-zomi" lang={LANG_ATTR[shown.target.code]}>{sides.target}</p>
                  {match.reference && <p className="tr-reference">{match.reference}</p>}
                </li>
                );
              })}
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
            <p className="font-playfair tr-empty-title">Look up {chosen.source.name} → {chosen.target.name}</p>
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
            {selected === "en-zom" && (
              <>
                <div className="word-section-label">Try</div>
                <div className="tr-suggestions">
                  {EXAMPLES.map((item) => (
                    <button key={item} type="button" className="tr-suggestion" onClick={() => { setText(item); submit(item); }}>{item}</button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
      <div className="screen-pad" />
    </div>
  );
}
