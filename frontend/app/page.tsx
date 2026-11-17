import Image from "next/image";
import Link from "next/link";
<<<<<<< HEAD
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
=======
import { IconArrow, IconBook, IconSearch } from "@/components/Icons";
import { getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";
import type { DictionaryEntry } from "@/lib/api";
import { SITE_URL, websiteJsonLd } from "@/lib/site";
import "./siamsil-home.css";

const FEATURES: Array<{ href: string; title: string; subtitle: string; tile: string }> = [
  { href: "/zomidictionary", title: "Dictionary", subtitle: "Look up English and Zomi words", tile: "dictionary" },
  { href: "/zomitranslate", title: "Translate", subtitle: "Find stored translations", tile: "translate" },
  { href: "/bible", title: "Bible", subtitle: "Read, search and study", tile: "bible" },
  { href: "/library", title: "Library", subtitle: "Books and cultural archives", tile: "library" },
  { href: "/learning", title: "Learn", subtitle: "Lessons and reviewed phrases", tile: "learn" },
  { href: "/chat", title: "AI Tools", subtitle: "Source-grounded language help", tile: "ai" },
];
function StatIcon({ kind }: { kind: "words" | "sentences" | "verses" | "global" }) {
  const glyph = { words: "book", sentences: "document", global: "globe" }[kind as "words" | "sentences" | "global"];
  if (glyph) return <span className="st-stat-glyph" style={{ ["--glyph" as string]: `url(/theme/stat-${glyph}.png)` }} aria-hidden="true" />;
  return <svg width={40} height={40} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 4v16M8 8h8" /><rect x="4" y="3" width="16" height="18" rx="2" /></svg>;
}
const STAT_KINDS: Record<string, "words" | "sentences" | "verses"> = { "Dictionary entries": "words", "Example sentences": "sentences", "Bible verses": "verses" };
const RESOURCES = [
  { href: "/bible", title: "Zomi Bible", note: "Read and study", photo: "bible" },
  { href: "/library", title: "Library", note: "Explore books and archives", photo: "books" },
  { href: "/learning", title: "Learning", note: "Practice reviewed lessons", photo: "learn" },
  { href: "/resources", title: "Resources", note: "What Siamsil holds", photo: "culture" },
];
const SUGGESTIONS = ["water", "family", "thank you", "school", "love", "God"];
function compact(value: number) {
>>>>>>> origin/main
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 10_000) return `${Math.round(value / 1000)}K`;
  return value.toLocaleString();
}
async function loadHome() {
<<<<<<< HEAD
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
=======
  const [health, verse, word] = await Promise.allSettled([getHealth(), getDailyVerse(), getWordOfDay()]);
  const language = health.status === "fulfilled" ? (health.value.language as Record<string, number> | null | undefined) : undefined;
  const metadata = health.status === "fulfilled" ? (health.value.metadata?.counts as Record<string, number> | undefined) : undefined;
  const stats = [
    { label: "Dictionary entries", value: language?.dictionary_entries ?? 0 },
    { label: "Example sentences", value: language?.parallel_sentences ?? 0 },
    { label: "Bible verses", value: metadata?.bible_verses ?? 0 },
  ].filter(({ value }) => value > 0);
  return { stats, entries: language?.dictionary_entries ?? 0, verse: verse.status === "fulfilled" ? verse.value : null, word: word.status === "fulfilled" ? word.value : null };
}
function WordPanel({ word }: { word: DictionaryEntry | null }) {
  return <section className="sr-panel" aria-labelledby="sr-word-heading">
    <div className="sr-panel-head"><div><span className="sr-eyebrow sr-eyebrow-dark">THU TAWLBANG</span><h2 id="sr-word-heading">Word of the Day</h2></div><Link href="/zomidictionary">Dictionary →</Link></div>
    {word ? <>
      <div className="sr-word">{word.english}</div>
      <p className="sr-word-meaning">{word.zomi || word.definition || "Definition not available"}{word.part_of_speech ? ` · ${word.part_of_speech}` : ""}</p>
      <Link href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} className="sr-resource"><span className="sr-resource-icon"><IconBook size={19} /></span><span><strong>Read full entry</strong><small>{word.verified ? "Verified entry" : "Unreviewed entry"}</small></span><IconArrow size={15}/></Link>
    </> : <p className="sr-verse-empty">Word of the day will appear once the dictionary API is available.</p>}
  </section>;
>>>>>>> origin/main
}
export default async function Home() {
<<<<<<< HEAD
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
=======
  const { stats, entries, verse, word } = await loadHome();
  return <div className="sr-home">
    {SITE_URL && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: websiteJsonLd(SITE_URL) }} />}
    <section className="sr-hero" aria-labelledby="sr-title">
      <div className="sr-hero-inner">
        <p className="sr-eyebrow">The digital home for the Zomi language</p>
        <h1 id="sr-title" className="font-playfair sr-title">Words, scripture<br/>and learning <em>in Zomi.</em></h1>
        <p className="sr-summary">Look up words, read the Bible, practice everyday phrases,<br />and find translations Siamsil already holds.</p>
        <form className="sr-search" action="/zomidictionary" method="GET" role="search">
          <IconSearch size={20} />
          <input type="search" name="q" placeholder="Search a word in English or Zomi…" aria-label="Search English or Zomi dictionary" required />
          <button type="submit">Search</button>
        </form>
        <div className="sr-quick"><span>Try:</span>{SUGGESTIONS.map(term => <Link className="sr-chip" key={term} href={`/zomidictionary?q=${encodeURIComponent(term)}`}>{term}</Link>)}</div>
      </div>
    </section>
    <div className="sr-content">
      <nav className="sr-features" aria-label="Explore Siamsil">
        {FEATURES.map(({href,title,subtitle,tile}) => <Link className="sr-feature" href={href} key={href}>
          <Image className="sr-feature-tile" src={`/theme/tile-${tile}.png`} alt="" width={74} height={74} unoptimized />
          <span className="sr-feature-title">{title}</span>
          <span className="sr-feature-copy">{href === "/zomidictionary" && entries > 0 ? `${compact(entries)} words and growing` : subtitle}</span>
          <IconArrow className="sr-feature-arrow" size={17}/>
        </Link>)}
      </nav>
      {stats.length > 0 && <dl className="sr-metrics">{stats.map(stat => <div className="sr-metric" key={stat.label}><span className="sr-metric-icon"><StatIcon kind={STAT_KINDS[stat.label]} /></span><div><dd><strong>{compact(stat.value)}</strong></dd><dt><span>{stat.label}</span></dt></div></div>)}<div className="sr-metric"><span className="sr-metric-icon"><StatIcon kind="global" /></span><div><dd><strong>Global</strong></dd><dt><span>For the Zomi community worldwide</span></dt></div></div></dl>}
      <div className="sr-cards">
        <section className="sr-panel" aria-labelledby="sr-verse-heading">
          <div className="sr-panel-head"><div><span className="sr-eyebrow sr-eyebrow-dark">NISIM THALAKNA</span><h2 id="sr-verse-heading">Daily Verse</h2></div><Link href="/bible">Read Bible →</Link></div>
          <div className="sr-verse-box">{verse ? <><p lang="ctd">{verse.zomi_iso}</p><small>{verse.reference}</small></> : <p className="sr-verse-empty">Daily verse is temporarily unavailable. Visit the Bible reader to explore scripture.</p>}</div>
        </section>
        <WordPanel word={word} />
        <section className="sr-panel" aria-labelledby="sr-resources-heading">
          <div className="sr-panel-head"><h2 id="sr-resources-heading">Featured Resources</h2><Link href="/library">View all →</Link></div>
          <div className="sr-resources-grid">
            {RESOURCES.map(({ href, title, note, photo }) => <Link href={href} className="sr-resource sr-resource-photo" key={href}>
              <Image src={`/theme/photo-${photo}.webp`} alt="" width={120} height={120} unoptimized />
              <span><strong>{title}</strong><small>{note}</small></span>
            </Link>)}
          </div>
        </section>
      </div>
      <p className="sr-note">Siamsil identifies sources and labels unreviewed machine translations. Dictionary, verse and word-of-day data are loaded from the existing API.</p>
>>>>>>> origin/main
    </div>
  </div>;
}
