import Link from "next/link";
import { IconArrow, IconBook, IconCross, IconAcademic, IconTranslate, IconChat, IconLibrary } from "@/components/Icons";
import { getDailyVerse, getHealth, getWordOfDay } from "@/lib/api";

function formatCount(value?: number) {
  return value ? value.toLocaleString() : "—";
}

function numericCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

const destinations = [
  { href: "/zomidictionary", Icon: IconBook, title: "Dictionary", detail: "Find words and meanings", className: "home-destination-featured" },
  { href: "/zomitranslate", Icon: IconTranslate, title: "Translate", detail: "Explore known sentence pairs", className: "" },
  { href: "/learning", Icon: IconAcademic, title: "Learning", detail: "Build your Zomi fluency", className: "" },
  { href: "/library", Icon: IconLibrary, title: "Library", detail: "Read books and archives", className: "" },
  { href: "/bible", Icon: IconCross, title: "Bible", detail: "Read the Laisiangtho", className: "" },
  { href: "/chat", Icon: IconChat, title: "Siamsil AI", detail: "Ask about the language", className: "" },
];

export default async function Home() {
  let verse = null;
  let word = null;
  let dictionaryCount = 0;
  let parallelCount = 0;
  let bibleCount = 0;

  try {
    const health = await getHealth();
    dictionaryCount = numericCount(health.language?.dictionary_entries);
    parallelCount = numericCount(health.language?.parallel_sentences);
    const counts = health.metadata?.counts as Record<string, number> | undefined;
    bibleCount = counts?.bible_verses ?? 0;
  } catch {
    /* Health is optional for first paint. */
  }
  try { verse = await getDailyVerse(); } catch {}
  try { word = await getWordOfDay(); } catch {}

  return (
    <div className="home-root">
      <section className="home-daily" aria-label="Daily verse">
        <div className="home-daily-band"><span>Nisim Thalakna · Daily Verse</span></div>
        <div className="home-daily-card">
          <span className="font-playfair home-daily-quote" aria-hidden="true">“</span>
          <div>
          {verse ? (
            <>
              <blockquote className="font-playfair">{verse.zomi_iso}</blockquote>
              <span className="home-daily-ref">— {verse.reference}</span>
            </>
          ) : <p className="home-daily-empty">Daily verse will appear when the API is running.</p>}
          </div>
        </div>
      </section>

    <div className="home-page">
      <section className="home-explore" aria-labelledby="explore-heading">
        <div className="home-section-heading">
          <div><span className="home-section-kicker">What would you like to do?</span><h2 id="explore-heading" className="font-playfair">Explore Siamsil</h2></div>
          <span className="home-section-decoration" aria-hidden="true" />
        </div>
        <div className="home-destinations">
          {destinations.map(({ href, Icon, title, detail, className }) => (
            <Link href={href} className={`home-destination ${className}`} key={href}>
              <span className="home-destination-icon"><Icon size={22} /></span>
              <span className="home-destination-copy"><span className="font-playfair home-destination-title">{title}</span><span className="home-destination-detail">{detail}</span></span>
              <span className="home-destination-arrow"><IconArrow size={15} /></span>
            </Link>
          ))}
        </div>
      </section>

      <div className="home-lower-grid">
        <section className="home-word-panel" aria-labelledby="word-heading">
          <div className="home-panel-heading"><span className="home-section-kicker">A little something to learn</span><h2 id="word-heading" className="font-playfair">Word of the day</h2></div>
          {word ? (
            <div className="home-word-content">
              <span className="home-word-label">Thu Tawlbang</span>
              <div className="home-word-line"><span className="font-playfair home-word-title">{word.english}</span>{word.part_of_speech && <span className="home-word-pos">{word.part_of_speech}</span>}</div>
              {word.zomi && <p className="home-word-zomi">{word.zomi}</p>}
              {word.definition && <p className="home-word-definition">{word.definition}</p>}
              {!word.verified && <p className="home-word-definition">Source dictionary entry · not yet reviewer-verified</p>}
              <Link href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} className="home-text-link">View full entry <IconArrow size={14} /></Link>
            </div>
          ) : <p className="home-panel-empty">The daily word will appear when the dictionary is available.</p>}
        </section>
        <section className="home-collection-panel" aria-labelledby="collection-heading">
          <div className="home-panel-heading"><span className="home-section-kicker">A growing collection</span><h2 id="collection-heading" className="font-playfair">Made for our language</h2></div>
          <div className="home-collection-stats">
            <div><strong className="font-playfair">{formatCount(dictionaryCount)}</strong><span>Dictionary entries</span></div>
            <div><strong className="font-playfair">{formatCount(parallelCount)}</strong><span>Sentence pairs</span></div>
            <div><strong className="font-playfair">{formatCount(bibleCount)}</strong><span>Bible verses</span></div>
          </div>
          <p>Explore a living resource for Zomi readers, learners, and families.</p>
        </section>
      </div>
    </div>
    </div>
  );
}
