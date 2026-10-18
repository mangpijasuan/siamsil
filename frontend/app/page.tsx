import Link from "next/link";
import type { ComponentType } from "react";
import RecentSearches from "@/components/RecentSearches";
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
import { getBibleVersions, getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";
import type { BibleVerse, DictionaryEntry } from "@/lib/api";

type IconType = ComponentType<{ size?: number; className?: string }>;

const QUICK_SEARCHES = ["water", "family", "thank you", "school", "love", "God"];

function formatCount(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 10_000) return `${Math.round(value / 1000)}K`;
  return value.toLocaleString();
}

async function loadHome() {
  const [health, verse, word, versions] = await Promise.allSettled([
    getHealth(), getDailyVerse(), getWordOfDay(), getBibleVersions(),
  ]);
  const language = health.status === "fulfilled"
    ? (health.value.language as Record<string, number> | null | undefined)
    : undefined;
  const bibleVersions = versions.status === "fulfilled" ? versions.value.versions : [];
  const bibleLanguages = [...new Set(bibleVersions.map((item) => item.language_name).filter(Boolean))] as string[];
  return {
    entries: language?.dictionary_entries ?? 0,
    sentences: language?.parallel_sentences ?? 0,
    bibleVersions: bibleVersions.length,
    bibleLanguages,
    verse: verse.status === "fulfilled" ? verse.value : null,
    word: word.status === "fulfilled" ? word.value : null,
  };
}

function DailyVerse({ verse }: { verse: BibleVerse | null }) {
  return (
    <section className="hx-card hx-verse" aria-labelledby="hx-verse-title">
      <p className="hx-eyebrow">Nisim Thalakna</p>
      <h2 className="font-playfair hx-card-title" id="hx-verse-title">Daily Verse</h2>
      {verse ? (
        <figure className="hx-verse-box">
          <span className="font-playfair hx-verse-mark" aria-hidden="true">&ldquo;</span>
          <blockquote>
            <p className="font-playfair hx-verse-zomi" lang="zom">{verse.zomi_iso}</p>
            {verse.english && <p className="hx-verse-en" lang="en">{verse.english}</p>}
          </blockquote>
          <figcaption className="hx-verse-foot">
            <span>{verse.reference}</span>
            <Link href={`/bible?book=${verse.book_id}&chapter=${verse.chapter}`} className="hx-link">
              Read in Bible <IconArrow size={12} />
            </Link>
          </figcaption>
        </figure>
      ) : (
        <p className="hx-empty">The daily verse appears here when the Bible is loaded.</p>
      )}
    </section>
  );
}

function WordOfDay({ word }: { word: DictionaryEntry | null }) {
  return (
    <section className="hx-card" aria-labelledby="hx-word-title">
      <div className="hx-card-head">
        <div>
          <p className="hx-eyebrow">Thu Tawlbang</p>
          <h2 className="font-playfair hx-card-title" id="hx-word-title">Word of the Day</h2>
        </div>
        {word?.part_of_speech && <span className="hx-pill">{word.part_of_speech}</span>}
      </div>
      {word ? (
        <>
          <p className="font-playfair hx-word">{word.english}</p>
          {(word.zomi || word.definition) && <p className="hx-word-zomi" lang="zom">{word.zomi || word.definition}</p>}
          <div className="hx-verse-foot">
            <span>{word.verified ? "Verified entry" : "Unreviewed entry"}</span>
            <Link href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} className="hx-link">
              Full entry <IconArrow size={12} />
            </Link>
          </div>
        </>
      ) : (
        <p className="hx-empty">A new dictionary word appears here each day once the dictionary is loaded.</p>
      )}
    </section>
  );
}

export default async function Home() {
  const { entries, sentences, bibleVersions, bibleLanguages, verse, word } = await loadHome();

  const features: Array<{ href: string; title: string; text: string; Icon: IconType; tone: string }> = [
    { href: "/zomidictionary", title: "Dictionary", text: entries ? `${formatCount(entries)} words and growing` : "Zomi and English words", Icon: IconBook, tone: "gold" },
    { href: "/zomitranslate", title: "Translate", text: "Zomi ↔ English, from stored pairs", Icon: IconTranslate, tone: "blue" },
    { href: "/bible", title: "Bible", text: "Read, search and compare", Icon: IconCross, tone: "green" },
    { href: "/library", title: "Library", text: "Books and archives in Zomi", Icon: IconLibrary, tone: "violet" },
    { href: "/learning", title: "Learn", text: "Phrases and the citizenship test", Icon: IconAcademic, tone: "rose" },
    { href: "/chat", title: "Siamsil AI", text: "Answers from Siamsil's own data", Icon: IconChat, tone: "sky" },
  ];

  const stats = [
    { value: entries, label: "Dictionary entries", Icon: IconBook },
    { value: sentences, label: "Example sentences", Icon: IconTranslate },
    { value: bibleVersions, label: "Bible versions", note: bibleLanguages.join(" · "), Icon: IconCross },
  ].filter((stat) => stat.value > 0);

  return (
    <div className="hx">
      <section className="hx-hero">
        <div className="hx-hero-copy">
          <p className="hx-kicker">The digital home for the Zomi language</p>
          <h1 className="font-playfair hx-title">
            Words, scripture and learning <span className="hx-title-accent">in Zomi.</span>
          </h1>
          <p className="hx-lede">
            Look up words, read the Bible, practice everyday phrases, and find translations Siamsil already holds.
          </p>
          <form action="/zomidictionary" method="GET" className="hx-search" role="search">
            <IconSearch size={20} className="hx-search-icon" />
            <input name="q" type="search" placeholder="Search a word in English or Zomi…" aria-label="Search the dictionary" />
            <button type="submit">Search</button>
          </form>
          <div className="hx-quick">
            <span>Try:</span>
            {QUICK_SEARCHES.map((term) => (
              <Link key={term} href={`/zomidictionary?q=${encodeURIComponent(term)}`} className="hx-chip">{term}</Link>
            ))}
          </div>
        </div>
        <div className="hx-hero-art" aria-hidden="true">
          <p className="font-playfair hx-quote">&ldquo;Language connects people, knowledge builds communities.&rdquo;</p>
        </div>
      </section>

      <div className="hx-body">
        <nav className="hx-features" aria-label="Siamsil sections">
          {features.map(({ href, title, text, Icon, tone }) => (
            <Link key={href} href={href} className={`hx-feature hx-tone-${tone}`}>
              <span className="hx-feature-icon"><Icon size={24} /></span>
              <span className="hx-feature-copy">
                <span className="font-playfair hx-feature-title">{title}</span>
                <span className="hx-feature-text">{text}</span>
              </span>
              <IconArrow size={16} className="hx-feature-arrow" />
            </Link>
          ))}
        </nav>

        {stats.length > 0 && (
          <dl className="hx-stats">
            {stats.map(({ value, label, note, Icon }) => (
              <div key={label} className="hx-stat">
                <span className="hx-stat-icon"><Icon size={30} /></span>
                <div>
                  <dd className="font-playfair hx-stat-value">{formatCount(value)}</dd>
                  <dt className="hx-stat-label">{label}</dt>
                  {note && <span className="hx-stat-note">{note}</span>}
                </div>
              </div>
            ))}
          </dl>
        )}

        <div className="hx-row">
          <DailyVerse verse={verse} />
          <WordOfDay word={word} />
          <RecentSearches />
        </div>

        <p className="hx-trust">
          Siamsil never invents Zomi. Every result shows where it comes from, and machine-translated examples are
          labeled until people have checked them.
        </p>
      </div>
    </div>
  );
}
