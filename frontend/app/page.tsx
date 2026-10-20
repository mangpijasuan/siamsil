import Link from "next/link";
import type { ComponentType } from "react";
import { IconAcademic, IconArrow, IconBook, IconChat, IconCross, IconLibrary, IconSearch, IconTranslate } from "@/components/Icons";
import { getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";
import type { DictionaryEntry } from "@/lib/api";
import "./siamsil-home.css";

type IconType = ComponentType<{ size?: number; className?: string }>;
const FEATURES: Array<{ href: string; title: string; subtitle: string; Icon: IconType }> = [
  { href: "/zomidictionary", title: "Dictionary", subtitle: "Look up English and Zomi words", Icon: IconBook },
  { href: "/zomitranslate", title: "Translate", subtitle: "Find stored translations", Icon: IconTranslate },
  { href: "/bible", title: "Bible", subtitle: "Read, search and study", Icon: IconCross },
  { href: "/library", title: "Library", subtitle: "Books and cultural archives", Icon: IconLibrary },
  { href: "/learning", title: "Learn", subtitle: "Lessons and reviewed phrases", Icon: IconAcademic },
  { href: "/chat", title: "AI Tools", subtitle: "Source-grounded language help", Icon: IconChat },
];
const SUGGESTIONS = ["water", "family", "thank you", "school", "love", "God"];
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
  return { stats, verse: verse.status === "fulfilled" ? verse.value : null, word: word.status === "fulfilled" ? word.value : null };
}
function WordPanel({ word }: { word: DictionaryEntry | null }) {
  return <section className="sr-panel" aria-labelledby="sr-word-heading">
    <div className="sr-panel-head"><div><span className="sr-eyebrow">Thu Tawlbang</span><h2 id="sr-word-heading">Word of the Day</h2></div><Link href="/zomidictionary">Dictionary →</Link></div>
    {word ? <>
      <div className="sr-word">{word.english}</div>
      <p className="sr-word-meaning">{word.zomi || word.definition || "Definition not available"}{word.part_of_speech ? ` · ${word.part_of_speech}` : ""}</p>
      <Link href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} className="sr-resource"><span className="sr-resource-icon"><IconBook size={19} /></span><span><strong>Read full entry</strong><small>{word.verified ? "Verified entry" : "Unreviewed entry"}</small></span><IconArrow size={15}/></Link>
    </> : <p className="sr-verse-empty">Word of the day will appear once the dictionary API is available.</p>}
  </section>;
}
export default async function Home() {
  const { stats, verse, word } = await loadHome();
  return <div className="sr-home">
    <section className="sr-hero" aria-labelledby="sr-title">
      <div className="sr-hero-inner">
        <p className="sr-eyebrow">The digital home for the Zomi language</p>
        <h1 id="sr-title" className="font-playfair sr-title">Words, scripture<br/>and learning <em>in Zomi.</em></h1>
        <p className="sr-summary">Look up words, read the Bible, practice everyday phrases, and explore translations Siamsil already holds — always with the source shown.</p>
        <form className="sr-search" action="/zomidictionary" method="GET" role="search">
          <IconSearch size={20} />
          <input type="search" name="q" placeholder="Search a word in English or Zomi…" aria-label="Search dictionary" required />
          <button type="submit">Search</button>
        </form>
        <div className="sr-quick"><span>Try:</span>{SUGGESTIONS.map(term => <Link className="sr-chip" key={term} href={`/zomidictionary?q=${encodeURIComponent(term)}`}>{term}</Link>)}</div>
      </div>
    </section>
    <div className="sr-content">
      <nav className="sr-features" aria-label="Explore Siamsil">
        {FEATURES.map(({href,title,subtitle,Icon}) => <Link className="sr-feature" href={href} key={href}>
          <span className="sr-feature-icon"><Icon size={24}/></span>
          <span className="sr-feature-title">{title}</span><span className="sr-feature-copy">{subtitle}</span>
          <IconArrow className="sr-feature-arrow" size={17}/>
        </Link>)}
      </nav>
      {stats.length > 0 && <dl className="sr-metrics">{stats.map(stat => <div className="sr-metric" key={stat.label}><dd><strong>{compact(stat.value)}</strong></dd><dt><span>{stat.label}</span></dt></div>)}<div className="sr-metric"><dd><strong>Global</strong></dd><dt><span>For the Zomi community worldwide</span></dt></div></dl>}
      <div className="sr-cards">
        <section className="sr-panel" aria-labelledby="sr-verse-heading">
          <div className="sr-panel-head"><div><span className="sr-eyebrow">Nisim Thalakna</span><h2 id="sr-verse-heading">Daily Verse</h2></div><Link href="/bible">Read Bible →</Link></div>
          <div className="sr-verse-box">{verse ? <><p lang="zom">{verse.zomi_iso}</p><small>{verse.reference}</small></> : <p className="sr-verse-empty">Daily verse is temporarily unavailable. Visit the Bible reader to explore scripture.</p>}</div>
        </section>
        <WordPanel word={word} />
        <section className="sr-panel" aria-labelledby="sr-resources-heading">
          <div className="sr-panel-head"><h2 id="sr-resources-heading">Featured Resources</h2><Link href="/library">View all →</Link></div>
          <Link href="/bible" className="sr-resource"><span className="sr-resource-icon"><IconCross size={21}/></span><span><strong>Zomi Bible</strong><small>Read and study</small></span></Link>
          <Link href="/library" className="sr-resource"><span className="sr-resource-icon"><IconLibrary size={21}/></span><span><strong>Library</strong><small>Explore books and archives</small></span></Link>
          <Link href="/learning" className="sr-resource"><span className="sr-resource-icon"><IconAcademic size={21}/></span><span><strong>Learning</strong><small>Practice reviewed lessons</small></span></Link>
          <Link href="/chat" className="sr-resource"><span className="sr-resource-icon"><IconChat size={21}/></span><span><strong>Siamsil AI</strong><small>Answers grounded in available sources</small></span></Link>
        </section>
      </div>
      <p className="sr-note">Siamsil identifies sources and labels unreviewed machine translations. Dictionary, verse and word-of-day data are loaded from the existing API.</p>
    </div>
  </div>;
}
