import Link from "next/link";
import type { ComponentType } from "react";
import {
  IconAcademic,
  IconArrow,
  IconBook,
  IconChat,
  IconCross,
  IconLibrary,
  IconSearch,
  IconTranslate,
} from "@/components/Icons";
import { getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";
import type { DictionaryEntry } from "@/lib/api";

type IconType = ComponentType<{ size?: number; className?: string }>;

const EXPLORE: Array<{ href: string; title: string; text: string; Icon: IconType; tone: string }> = [
  { href: "/zomidictionary", title: "Dictionary", text: "English headwords with Zomi definitions", Icon: IconBook, tone: "navy" },
  { href: "/zomitranslate", title: "Translate", text: "Look up stored English and Zomi pairs", Icon: IconTranslate, tone: "gold" },
  { href: "/bible", title: "Bible", text: "Laisiangtho, 66 books with English alongside", Icon: IconCross, tone: "navy" },
  { href: "/learning", title: "Learning", text: "Teacher-reviewed phrases and the citizenship test", Icon: IconAcademic, tone: "gold" },
  { href: "/library", title: "Library", text: "Books, archives, and collections in Zomi", Icon: IconLibrary, tone: "navy" },
  { href: "/chat", title: "Siamsil AI", text: "Answers drawn only from Siamsil's own data", Icon: IconChat, tone: "gold" },
];

const QUICK_SEARCHES = ["water", "family", "thank you", "school"];

function formatCount(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 10_000) return `${Math.round(value / 1000)}K`;
  return value.toLocaleString();
}

async function loadHome() {
  const [health, verse, word] = await Promise.allSettled([getHealth(), getDailyVerse(), getWordOfDay()]);
  const language = health.status === "fulfilled"
    ? (health.value.language as Record<string, number> | null | undefined)
    : undefined;
  const metadataCounts = health.status === "fulfilled"
    ? (health.value.metadata?.counts as Record<string, number> | undefined)
    : undefined;
  const stats = [
    { value: language?.dictionary_entries ?? 0, label: "Dictionary entries" },
    { value: metadataCounts?.bible_verses ?? 0, label: "Bible verses" },
    { value: language?.parallel_sentences ?? 0, label: "Example sentences" },
  ].filter((stat) => stat.value > 0);
  return {
    stats,
    verse: verse.status === "fulfilled" ? verse.value : null,
    word: word.status === "fulfilled" ? word.value : null,
  };
}

function WordCard({ word }: { word: DictionaryEntry | null }) {
  return (
    <section className="hm-card hm-word" aria-labelledby="hm-word-title">
      <div className="hm-card-head">
        <span className="hm-eyebrow" id="hm-word-title">Thu Tawlbang · Word of the day</span>
        {word?.part_of_speech && <span className="hm-pos">{word.part_of_speech}</span>}
      </div>
      {word ? (
        <>
          <div className="font-playfair hm-word-en">{word.english}</div>
          {(word.zomi || word.definition) && <p className="hm-word-zomi">{word.zomi || word.definition}</p>}
          <div className="hm-card-foot">
            <span className="hm-status">{word.verified ? "Verified entry" : "Unreviewed entry"}</span>
            <Link href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} className="hm-link">
              Full entry <IconArrow size={12} />
            </Link>
          </div>
        </>
      ) : (
        <p className="hm-empty">A new dictionary word appears here each day once the dictionary is loaded.</p>
      )}
    </section>
  );
}

export default async function Home() {
  const { stats, verse, word } = await loadHome();

  return (
    <div className="hm-root">
      <div className="home-hero">
        <div className="home-hero-label">Nisim Thalakna · Daily Verse</div>
      </div>

      <div style={{ padding: "0 16px", marginTop: -24, marginBottom: 4 }}>
        <div style={{
          background: "var(--white)",
          borderRadius: "var(--radius-lg)",
          padding: "20px 20px 20px 18px",
          boxShadow: "var(--shadow-lg)",
          borderLeft: "3px solid var(--gold)",
          display: "flex",
          alignItems: "flex-start",
          gap: 12,
        }}>
          <div className="font-playfair" style={{
            fontSize: 52, lineHeight: 0.7, color: "var(--gold)",
            opacity: 0.55, flexShrink: 0, marginTop: 6, userSelect: "none",
          }}>&ldquo;</div>
          <div style={{ flex: 1 }}>
            {verse ? (
              <>
                <p className="font-playfair" style={{
                  fontSize: 13.5, fontStyle: "italic", color: "var(--navy)",
                  lineHeight: 1.7, margin: "0 0 10px",
                }}>
                  {verse.zomi_iso}
                </p>
                <p style={{ fontSize: 10, color: "var(--gray)", fontWeight: 600, letterSpacing: "0.05em" }}>
                  — {verse.reference}
                </p>
              </>
            ) : (
              <p style={{ fontSize: 13, color: "var(--gray)", margin: 0 }}>
                Daily verse will appear when the API is running.
              </p>
            )}
          </div>
        </div>
      </div>

      <section className="hm-hero">
        <div className="hm-hero-inner">
          <p className="hm-kicker">The digital home for the Zomi language</p>
          <h1 className="font-playfair hm-title">
            Words, scripture and learning<span className="hm-title-accent"> in Zomi.</span>
          </h1>
          <p className="hm-lede">
            Look up words, read the Bible, practice everyday phrases, and find translations Siamsil already holds,
            always with the source shown.
          </p>

          <form action="/zomidictionary" method="GET" className="hm-search" role="search">
            <IconSearch size={18} className="hm-search-icon" />
            <input name="q" type="search" placeholder="Search a word in English or Zomi…" aria-label="Search the dictionary" />
            <button type="submit">Search</button>
          </form>
          <div className="hm-quick">
            <span>Try</span>
            {QUICK_SEARCHES.map((term) => (
              <Link key={term} href={`/zomidictionary?q=${encodeURIComponent(term)}`} className="hm-chip">{term}</Link>
            ))}
          </div>

          {stats.length > 0 && (
            <dl className="hm-stats" style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}>
              {stats.map((stat) => (
                <div key={stat.label} className="hm-stat">
                  <dt>{stat.label}</dt>
                  <dd className="font-playfair">{formatCount(stat.value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>

      <div className="hm-body">
        <div className="hm-section-head">
          <h2 className="font-playfair">Today</h2>
        </div>
        <div className="hm-today">
          <WordCard word={word} />
        </div>

        <div className="hm-section-head">
          <h2 className="font-playfair">Explore</h2>
        </div>
        <div className="hm-explore">
          {EXPLORE.map(({ href, title, text, Icon, tone }) => (
            <Link key={href} href={href} className={`hm-tile hm-tile-${tone}`}>
              <span className="hm-tile-icon"><Icon size={20} /></span>
              <span className="hm-tile-copy">
                <span className="hm-tile-title">{title}</span>
                <span className="hm-tile-text">{text}</span>
              </span>
              <IconArrow size={14} className="hm-tile-arrow" />
            </Link>
          ))}
        </div>

        <Link href="/learning/citizenship" className="hm-feature">
          <div>
            <span className="hm-eyebrow hm-eyebrow-light">Learning · Preview</span>
            <div className="font-playfair hm-feature-title">U.S. Citizenship Test practice</div>
            <p className="hm-feature-text">Study civics questions in English, Zomi, and Burmese.</p>
          </div>
          <span className="hm-feature-cta">Start practice <IconArrow size={14} /></span>
        </Link>

        <p className="hm-trust">
          Siamsil never invents Zomi. Every result shows where it comes from, and machine-translated examples are
          labeled until people have checked them.
        </p>
      </div>
      <div className="screen-pad" />
    </div>
  );
}
