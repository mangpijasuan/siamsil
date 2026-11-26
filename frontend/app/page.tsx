import Image from "next/image";
import Link from "next/link";
import { IconArrow, IconBook, IconSearch } from "@/components/Icons";
import { getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";
import type { DictionaryEntry } from "@/lib/api";
import { SITE_URL, websiteJsonLd } from "@/lib/site";
import "./siamsil-home.css";

const FEATURES: Array<{ href: string; title: string; subtitle: string; tile: string }> = [
  { href: "/zomidictionary", title: "Dictionary", subtitle: "Look up English and Zomi words, with their source", tile: "dictionary" },
  { href: "/zomitranslate", title: "Translate", subtitle: "Find stored translations. Unreviewed ones are labelled", tile: "translate" },
  { href: "/chat", title: "Siamsil AI", subtitle: "Source-grounded language help", tile: "ai" },
  { href: "/bible", title: "Bible", subtitle: "Read, search and study", tile: "bible" },
  { href: "/learning", title: "Learn", subtitle: "Lessons and reviewed phrases", tile: "learn" },
  // Church Hub is a static app, so it is a plain link; its tile is the sidebar's church glyph.
  { href: "/church-manager/index.html", title: "Church Hub", subtitle: "Private, in-browser tools for churches", tile: "church" },
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
// What anyone can use without paying or signing in. Every line matches what the app does today (see /about).
const FREE_TOOLS = [
  "Dictionary lookup in English and Zomi",
  "The Zomi Bible versions Siamsil may show",
  "Translations Siamsil already holds, with their source",
  "Everyday phrases reviewed by Zomi teachers",
  "Siamsil AI answers that show where they come from",
  "Your own workspace of saved words and progress",
];
const DATA_PRINCIPLES = [
  { title: "Labelled honestly", text: "Machine-made translations are marked unreviewed. Siamsil does not approve its own translations." },
  { title: "People decide", text: "Only people decide what counts as correct Zomi, following the Siamsil Zomi Standard Form." },
  { title: "Sources respected", text: "Every source has a recorded permission status. Text Siamsil may not show is kept out." },
  { title: "Your data stays with you", text: "Saved words, searches and progress stay in your browser. There are no accounts yet." },
];
function compact(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (value >= 10_000) return `${Math.round(value / 1000)}K`;
  return value.toLocaleString();
}
async function loadHome() {
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
}
export default async function Home() {
  const { stats, entries, verse, word } = await loadHome();
  return <div className="sr-home">
    {SITE_URL && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: websiteJsonLd(SITE_URL) }} />}
    <section className="sr-hero" aria-labelledby="sr-title">
      <div className="sr-hero-inner">
        <p className="sr-eyebrow">Zomi language, free for everyone</p>
        <h1 id="sr-title" className="font-playfair sr-title">Preserve the language.<br/><em>Empower the future.</em></h1>
        <p className="sr-summary">Look up words, read the Bible, practice everyday phrases,{" "}<br />and find translations Siamsil already holds.</p>
        <form className="sr-search" action="/zomidictionary" method="GET" role="search">
          <IconSearch size={20} />
          <input type="search" name="q" placeholder="Search a word in English or Zomi…" aria-label="Search English or Zomi dictionary" required />
          <button type="submit">Search</button>
        </form>
        <div className="sr-quick"><span>Try:</span>{SUGGESTIONS.map(term => <Link className="sr-chip" key={term} href={`/zomidictionary?q=${encodeURIComponent(term)}`}>{term}</Link>)}</div>
        <div className="sr-ctas">
          <Link className="sr-cta" href="#free-tools">Explore free tools</Link>
          <Link className="sr-cta sr-cta-quiet" href="/workspace">Open my workspace</Link>
        </div>
      </div>
    </section>
    <div className="sr-content">
      <h2 id="free-tools" className="sr-section-title font-playfair">Everything you need to explore Zomi</h2>
      <nav className="sr-features" aria-label="Explore Siamsil">
        {FEATURES.map(({href,title,subtitle,tile}) => <Link className="sr-feature" href={href} key={href}>
          <Image className="sr-feature-tile" src={tile === "church" ? "/theme/nav-church.png" : `/theme/tile-${tile}.png`} alt="" width={74} height={74} unoptimized />
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
      <div className="sr-about">
        <section className="sr-panel sr-free" aria-labelledby="sr-free-heading">
          <span className="sr-eyebrow sr-eyebrow-dark">FREE TO USE</span>
          <h2 id="sr-free-heading">Zomi belongs to everyone</h2>
          <p className="sr-about-lede">Every tool on Siamsil is free, and no account is needed.</p>
          <ul className="sr-free-list">{FREE_TOOLS.map(item => <li key={item}>{item}</li>)}</ul>
          <Link className="sr-cta sr-cta-dark" href="/workspace">Open my workspace</Link>
        </section>
        <section className="sr-panel" aria-labelledby="sr-data-heading">
          <div className="sr-panel-head"><div><span className="sr-eyebrow sr-eyebrow-dark">TRUST</span><h2 id="sr-data-heading">How Siamsil treats language data</h2></div><Link href="/resources">Our sources →</Link></div>
          <div className="sr-principles">{DATA_PRINCIPLES.map(({ title, text }) => <div key={title}><strong>{title}</strong><p>{text}</p></div>)}</div>
          <Link className="sr-more" href="/about">About Siamsil →</Link>
        </section>
      </div>
      <p className="sr-note">Siamsil identifies sources and labels unreviewed machine translations. Dictionary, verse and word-of-day data are loaded from the existing API.</p>
    </div>
  </div>;
}
