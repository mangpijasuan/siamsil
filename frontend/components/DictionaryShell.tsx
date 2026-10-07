"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import type { DictionaryEntry, TranslateMatch } from "@/lib/api";
import { getDictionaryEntry } from "@/lib/api";
import { pushHistory, useRecentSearches, useSavedWords } from "@/lib/localData";

const EXAMPLE_WORDS = ["water", "house", "mother", "eat", "love"];
const LETTERS = ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"];

function IconSearch() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  );
}
function IconBookmark({ filled }: { filled?: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
    </svg>
  );
}
function IconVerified() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  );
}
function IconClose() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  );
}

type Props = {
  entries: DictionaryEntry[];
  query: string;
  activeLetter: string;
  direction: "en-zom" | "zom-en";
  letters: Array<{ letter: string; count: number }>;
  error: string | null;
};

export default function DictionaryShell({ entries, query, activeLetter, direction, letters, error }: Props) {
  const [selected, setSelected] = useState<DictionaryEntry | null>(entries[0] ?? null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [exampleState, setExampleState] = useState<{ entryId: number; items: TranslateMatch[] } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const { isSaved, toggle } = useSavedWords();
  const recent = useRecentSearches("dictionary");
  const letterSet = new Set(letters.map((item) => item.letter));
  const selectedId = selected?.id;
  const examples = exampleState && exampleState.entryId === selectedId ? exampleState.items : [];

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    getDictionaryEntry(selectedId)
      .then((entry) => {
        if (!cancelled) {
          setSelected((current) => (current && current.id === entry.id ? { ...current, ...entry } : current));
          setExampleState({ entryId: entry.id, items: entry.examples ?? [] });
        }
      })
      .catch(() => {
        if (!cancelled) setExampleState({ entryId: selectedId, items: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (query) pushHistory("dictionary", query);
  }, [query]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setDetailOpen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  function selectEntry(entry: DictionaryEntry) {
    setSelected(entry);
    setDetailOpen(true);
  }

  function hrefFor(next: { letter?: string; dir?: string; q?: string }) {
    const params = new URLSearchParams();
    const qValue = next.q ?? query;
    const letterValue = next.letter ?? (activeLetter !== "All" ? activeLetter : "");
    const dirValue = next.dir ?? direction;
    if (qValue) params.set("q", qValue);
    if (letterValue && letterValue !== "All") params.set("letter", letterValue);
    if (dirValue === "zom-en") params.set("dir", "zom-en");
    const qs = params.toString();
    return qs ? `/zomidictionary?${qs}` : "/zomidictionary";
  }

  const showEmpty = !error && !query && activeLetter === "All" && entries.length === 0;
  const showNoResults = !error && (query || activeLetter !== "All") && entries.length === 0;

  return (
    <div className="dict-root">
      {/* ── Page header ── */}
      <div className="dict-header">
        <p className="gold-label" style={{ marginBottom: 6 }}>Siamsil</p>
        <h1 className="font-playfair dict-h1">Zomi Dictionary</h1>

        <div className="dict-search-row">
          <form action="/zomidictionary" method="GET" className="dict-search-form">
            <span className="dict-search-icon"><IconSearch /></span>
            <input
              name="q"
              type="search"
              defaultValue={query}
              placeholder="Search English or Zomi…"
              className="dict-search-input"
            />
            {direction === "zom-en" && <input type="hidden" name="dir" value="zom-en" />}
            {activeLetter !== "All" && <input type="hidden" name="letter" value={activeLetter} />}
            {query && (
              <Link href="/zomidictionary" className="dict-search-clear" aria-label="Clear">
                <IconClose />
              </Link>
            )}
          </form>

          <div className="lang-toggle dict-lang-toggle">
            <Link
              href={hrefFor({ dir: "zom-en" })}
              className={`lang-pill${direction === "zom-en" ? " active" : ""}`}
            >Zomi → EN</Link>
            <Link
              href={hrefFor({ dir: "en-zom" })}
              className={`lang-pill${direction === "en-zom" ? " active" : ""}`}
            >EN → Zomi</Link>
          </div>
        </div>
      </div>

      {/* ── Three-column body ── */}
      <div className="dict-body">

        {/* ── Word list ── */}
        <div className="dict-list-col" ref={listRef}>
          {/* Alphabet strip (horizontal on mobile, hidden on desktop — replaced by A-Z rail) */}
          <div className="alpha-strip dict-alpha-strip-mobile">
            {["All", ...LETTERS].map(l => (
              <Link
                key={l}
                href={l === "All" ? hrefFor({ letter: "All" }) : hrefFor({ letter: l })}
                className={`alpha-chip${activeLetter === l ? " active" : ""}`}
              >{l}</Link>
            ))}
          </div>

          {error && (
            <div className="dict-error">{error}</div>
          )}

          {showEmpty && (
            <div className="dict-empty">
              <div className="dict-empty-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--gray2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                </svg>
              </div>
              <p className="font-playfair" style={{ fontSize: 15, fontWeight: 700, color: "var(--navy)", marginBottom: 4 }}>Search the Zomi Dictionary</p>
              <p style={{ fontSize: 12, color: "var(--gray)" }}>Type a word above or tap a letter</p>
              {recent.length > 0 && (
                <div className="dict-suggest-group">
                  <div className="word-section-label">Recent</div>
                  <div className="dict-suggestions">
                    {recent.map((word) => (
                      <Link key={word} href={hrefFor({ q: word, letter: "All" })} className="dict-suggestion">{word}</Link>
                    ))}
                  </div>
                </div>
              )}
              <div className="dict-suggest-group">
                <div className="word-section-label">Try</div>
                <div className="dict-suggestions">
                  {EXAMPLE_WORDS.map((word) => (
                    <Link key={word} href={hrefFor({ q: word, letter: "All" })} className="dict-suggestion">{word}</Link>
                  ))}
                </div>
              </div>
            </div>
          )}

          {showNoResults && (
            <div className="dict-empty">
              <p className="font-playfair" style={{ fontSize: 15, fontWeight: 700, color: "var(--navy)" }}>No results for &ldquo;{query || activeLetter}&rdquo;</p>
              <p style={{ fontSize: 12, color: "var(--gray)" }}>
                {direction === "en-zom" ? "Try searching from Zomi instead, or check the spelling." : "Try searching from English instead, or check the spelling."}
              </p>
              <div className="dict-suggestions">
                <Link href={hrefFor({ dir: direction === "en-zom" ? "zom-en" : "en-zom" })} className="dict-suggestion">
                  {direction === "en-zom" ? "Search Zomi → EN" : "Search EN → Zomi"}
                </Link>
                {query && (
                  <Link href={`/zomitranslate?q=${encodeURIComponent(query)}`} className="dict-suggestion">Try Translate</Link>
                )}
                <Link href="/zomidictionary" className="dict-suggestion">Clear search</Link>
              </div>
            </div>
          )}

          {entries.length > 0 && (
            <>
              <div className="word-section-label" style={{ padding: "14px 20px 6px" }}>
                {query ? `${entries.length} results` : `${activeLetter} — ${entries.length} entries`}
              </div>
              {entries.map((entry) => (
                <button
                  key={entry.id}
                  type="button"
                  className={`word-item dict-word-btn${selected?.id === entry.id ? " featured" : ""}`}
                  onClick={() => selectEntry(entry)}
                >
                  <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
                    <div className="font-playfair" style={{ fontSize: 15, fontWeight: 700, color: "var(--navy)", lineHeight: 1.2 }}>{entry.english}</div>
                    {entry.zomi && <div style={{ fontSize: 11, color: "var(--gold)", fontStyle: "italic", marginTop: 2 }}>{entry.zomi}</div>}
                    {entry.definition && entry.definition !== entry.zomi && (
                      <div style={{ fontSize: 11, color: "var(--gray)", marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" }}>
                        {entry.definition}
                      </div>
                    )}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3, flexShrink: 0 }}>
                    {entry.part_of_speech && (
                      <span className="badge badge-cream">{entry.part_of_speech}</span>
                    )}
                    {entry.verified && (
                      <span style={{ color: "#16a34a", display: "flex" }}><IconVerified /></span>
                    )}
                  </div>
                </button>
              ))}
            </>
          )}
        </div>

        {/* ── A–Z index rail (desktop only) ── */}
        <nav className="dict-az-rail" aria-label="Alphabetical index">
          {LETTERS.map(l => {
            const hasEntries = letterSet.has(l);
            return (
              <Link
                key={l}
                href={hrefFor({ letter: l })}
                className={`dict-az-letter${activeLetter === l ? " active" : ""}${!hasEntries ? " dim" : ""}`}
                title={l}
                aria-disabled={!hasEntries}
              >{l}</Link>
            );
          })}
        </nav>

        {/* ── Detail panel (desktop sticky, mobile modal) ── */}
        <>
          {/* Mobile backdrop */}
          <div
            className={`dict-detail-backdrop${detailOpen ? " visible" : ""}`}
            onClick={() => setDetailOpen(false)}
          />
          <aside className={`dict-detail${detailOpen ? " mobile-open" : ""}`}>
            {selected ? (
              <>
                {/* Mobile close */}
                <button
                  type="button"
                  className="dict-detail-close"
                  onClick={() => setDetailOpen(false)}
                  aria-label="Close"
                >
                  <IconClose />
                </button>

                {/* Word + POS row */}
                <div className="dict-detail-top">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h2 className="font-playfair dict-detail-word">{selected.english}</h2>
                    {selected.zomi && (
                      <div className="dict-detail-zomi">{selected.zomi}</div>
                    )}
                  </div>
                  <button
                    type="button"
                    className={`dict-save-btn${isSaved(selected.id) ? " saved" : ""}`}
                    onClick={() => toggle({
                      id: selected.id,
                      english: selected.english,
                      zomi: selected.zomi ?? null,
                    })}
                    aria-label={isSaved(selected.id) ? "Unsave" : "Save word"}
                    title={isSaved(selected.id) ? "Saved on this device" : "Save word on this device"}
                  >
                    <IconBookmark filled={isSaved(selected.id)} />
                  </button>
                </div>

                {/* Tags row */}
                <div className="dict-detail-tags">
                  {selected.part_of_speech && (
                    <span className="badge badge-navy">{selected.part_of_speech}</span>
                  )}
                  {selected.domain && (
                    <span className="badge badge-cream">{selected.domain}</span>
                  )}
                  {selected.verified && (
                    <span className="badge dict-verified-badge">
                      <IconVerified /> Verified
                    </span>
                  )}
                  {selected.flagged && (
                    <span className="badge dict-review-badge">Needs review</span>
                  )}
                  {!selected.verified && !selected.flagged && (
                    <span className="badge badge-cream">Unreviewed</span>
                  )}
                </div>

                {/* Definition */}
                {(selected.zomi || selected.definition) && (
                  <div className="dict-detail-section">
                    <div className="dict-detail-label">Zomi definition</div>
                    {selected.zomi && selected.definition && selected.definition !== selected.zomi ? (
                      <>
                        <p className="dict-detail-zomi" style={{ marginBottom: 8 }}>{selected.zomi}</p>
                        <p className="dict-detail-def">{selected.definition}</p>
                      </>
                    ) : (
                      <p className="dict-detail-def">{selected.definition || selected.zomi}</p>
                    )}
                  </div>
                )}

                {selected.suggested_correction && (
                  <div className="dict-detail-section">
                    <div className="dict-detail-label">Suggested correction</div>
                    <p className="dict-detail-source">{selected.suggested_correction}</p>
                  </div>
                )}

                {examples.length > 0 && (
                  <div className="dict-detail-section">
                    <div className="dict-detail-label">Example sentences</div>
                    {examples.map((example, index) => (
                      <blockquote key={`${example.english}-${index}`} className="dict-detail-quote" style={{ marginBottom: 8 }}>
                        <div>{example.english}</div>
                        <div style={{ marginTop: 4 }}>{example.zomi}</div>
                        <div style={{ marginTop: 6, fontSize: 10, fontStyle: "normal", color: "var(--gray)" }}>
                          {example.label ?? "Machine-translated example (unverified)"}
                        </div>
                      </blockquote>
                    ))}
                  </div>
                )}

                {/* Source */}
                {selected.source && (
                  <div className="dict-detail-section">
                    <div className="dict-detail-label">Source</div>
                    <p className="dict-detail-source">{selected.source} · English headwords defined in Zomi</p>
                  </div>
                )}
              </>
            ) : (
              <div className="dict-detail-empty">
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--gray2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
                </svg>
                <p>Select a word to see its full entry</p>
              </div>
            )}
          </aside>
        </>
      </div>
    </div>
  );
}
